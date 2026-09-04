import json
from pathlib import Path

from django.conf import settings as django_settings
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from workspace.forms import FirstRunSetupForm
from workspace.models import Project, Skill, UserSettings
from workspace.seed import seed_demo_workspace
from workspace.services.filesystem import list_directory, read_text_file
from workspace.services.reporting import build_pdf, build_social_png
from workspace.services.state import ensure_settings, save_workspace_state, state_for_user

MAX_STATE_BYTES = 5_000_000


def _safe_filename(value, fallback="download.txt"):
    name = Path(str(value or fallback)).name.replace("\r", "").replace("\n", "").replace('"', "")
    return name or fallback


def login_router(request):
    if not User.objects.exists():
        return redirect("first_run_setup")
    return auth_views.LoginView.as_view(
        template_name="registration/login.html",
        extra_context={"pv_version": django_settings.PIXELVAULT_VERSION},
    )(request)

def first_run_setup(request):
    if User.objects.exists():
        return redirect("app" if request.user.is_authenticated else "login")
    if request.method == "POST":
        form = FirstRunSetupForm(request.POST)
        if form.is_valid():
            user = form.save()
            s = ensure_settings(user)
            s.display_name = form.cleaned_data["display_name"]
            s.workspace_name = form.cleaned_data["workspace_name"]
            s.save()
            if form.cleaned_data.get("seed_examples"):
                seed_demo_workspace(user)
            login(request, user)
            return redirect("app")
    else:
        form = FirstRunSetupForm()
    return render(
        request,
        "pixelvault/setup.html",
        {"form": form, "pv_version": django_settings.PIXELVAULT_VERSION},
    )


@ensure_csrf_cookie
@login_required
@require_GET
def app_view(request):
    ensure_settings(request.user)
    return render(request, "pixelvault/app.html", {"pv_version": django_settings.PIXELVAULT_VERSION})


@login_required
@require_http_methods(["GET", "PUT"])
def api_state(request):
    if request.method == "GET":
        return JsonResponse(state_for_user(request.user))
    if len(request.body) > MAX_STATE_BYTES:
        return JsonResponse({"error": "Workspace data is larger than the 5 MB save limit."}, status=413)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
        state = save_workspace_state(request.user, payload)
        return JsonResponse(state)
    except (json.JSONDecodeError, ValidationError) as exc:
        message = getattr(exc, "messages", None) or [str(exc)]
        return JsonResponse({"error": "Invalid workspace data", "details": message}, status=400)
    except Exception as exc:
        if django_settings.DEBUG:
            return JsonResponse({"error": str(exc)}, status=500)
        return JsonResponse({"error": "Could not save workspace."}, status=500)


@login_required
@require_GET
def backup_export(request):
    data = {"format": "pixelvault-django-backup", "version": 4, "exportedAt": timezone.now().isoformat(), "data": state_for_user(request.user)}
    response = JsonResponse(data, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = f'attachment; filename="pixelvault-backup-{timezone.localdate().isoformat()}.json"'
    return response


@login_required
@require_POST
def skill_upload(request, skill_id):
    skill = get_object_or_404(Skill, owner=request.user, pk=skill_id)
    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"error": "Choose a Markdown file."}, status=400)
    filename = _safe_filename(upload.name, "skill.md")
    if Path(filename).suffix.lower() not in {".md", ".markdown", ".txt"}:
        return JsonResponse({"error": "Only Markdown/text files are accepted."}, status=400)
    if upload.size > 2_000_000:
        return JsonResponse({"error": "Markdown file must be smaller than 2 MB."}, status=400)
    raw = upload.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = raw.decode("utf-8", errors="replace")
    upload.seek(0)
    skill.filename = filename
    skill.content = content
    if skill.attached_file:
        try:
            skill.attached_file.delete(save=False)
        except Exception:
            pass
    skill.attached_file.save(filename, upload, save=False)
    skill.updated_on = timezone.localdate()
    skill.save()
    return JsonResponse({"ok": True, "filename": skill.filename, "content": skill.content, "url": skill.attached_file.url if skill.attached_file else ""})


@login_required
@require_POST
def skill_write(request, skill_id):
    skill = get_object_or_404(Skill, owner=request.user, pk=skill_id)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)
    content = str(payload.get("content") or "")
    filename = _safe_filename(payload.get("filename") or skill.filename, "skill.md")
    skill.content = content
    skill.filename = filename
    # If a Markdown file is attached, rewrite the stored media file as well.
    if skill.attached_file:
        from django.core.files.base import ContentFile
        old_name = skill.attached_file.name
        storage = skill.attached_file.storage
        try:
            storage.delete(old_name)
        except Exception:
            pass
        skill.attached_file.save(filename, ContentFile(content.encode("utf-8")), save=False)
    skill.updated_on = timezone.localdate()
    skill.save()
    return JsonResponse({"ok": True, "filename": skill.filename, "content": skill.content, "url": skill.attached_file.url if skill.attached_file else ""})


@login_required
@require_GET
def skill_download(request, skill_id):
    skill = get_object_or_404(Skill, owner=request.user, pk=skill_id)
    response = HttpResponse(skill.content or "", content_type="text/markdown; charset=utf-8")
    filename = _safe_filename(skill.filename or f"{skill.name}.skill.md", "skill.md")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_GET
def project_tree(request, project_id):
    project = get_object_or_404(Project, owner=request.user, pk=project_id)
    settings_obj = ensure_settings(request.user)
    try:
        data = list_directory(project, settings_obj, request.GET.get("path", ""))
        return JsonResponse(data)
    except PermissionDenied as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    except ValidationError as exc:
        return JsonResponse({"error": "; ".join(exc.messages)}, status=400)


@login_required
@require_GET
def project_file(request, project_id):
    project = get_object_or_404(Project, owner=request.user, pk=project_id)
    settings_obj = ensure_settings(request.user)
    relative = request.GET.get("path", "")
    if not relative:
        return JsonResponse({"error": "Missing file path."}, status=400)
    try:
        return JsonResponse(read_text_file(project, settings_obj, relative))
    except PermissionDenied as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    except ValidationError as exc:
        return JsonResponse({"error": "; ".join(exc.messages)}, status=400)


@login_required
@require_GET
def project_preview(request, project_id, subpath=""):
    """Serve a static web project's files from its configured local path.

    This intentionally blocks dot-files and server-side source/config extensions.
    It is a convenience preview for static HTML/CSS/JS projects, not a process runner.
    """
    import mimetypes
    from workspace.services.filesystem import resolve_project_path

    project = get_object_or_404(Project, owner=request.user, pk=project_id)
    settings_obj = ensure_settings(request.user)
    relative = subpath or "index.html"
    parts = Path(relative).parts
    if any(part.startswith(".") for part in parts):
        raise Http404
    blocked = {".py", ".pyc", ".sqlite", ".sqlite3", ".db", ".pem", ".key", ".env", ".toml", ".ini", ".cfg"}
    try:
        root, target = resolve_project_path(project, settings_obj, relative)
    except (PermissionDenied, ValidationError):
        raise Http404
    if target.is_dir():
        target = target / "index.html"
    if not target.exists() or not target.is_file() or target.suffix.lower() in blocked:
        raise Http404
    mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    response = FileResponse(open(target, "rb"), content_type=mime)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    response["Content-Disposition"] = f'inline; filename="{_safe_filename(target.name, "preview")}"'
    response["Content-Security-Policy"] = (
        "sandbox allow-scripts; default-src 'self' data: blob:; "
        "script-src 'self' 'unsafe-inline' blob:; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'none'; "
        "object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    )
    return response


def _report_args(request):
    period = request.GET.get("period", "daily")
    if period not in {"daily", "weekly", "monthly"}:
        period = "daily"
    reference = parse_date(request.GET.get("date", "")) or timezone.localdate()
    privacy = request.GET.get("privacy", "full")
    if privacy not in {"full", "public", "showcase"}:
        privacy = "full"
    signature = request.GET.get("signature", "")[:80]
    return period, reference, privacy, signature


@login_required
@require_GET
def report_png(request):
    period, reference, privacy, signature = _report_args(request)
    static_root = Path(django_settings.BASE_DIR) / "static" / "pixelvault" / "assets"
    buf, data = build_social_png(
        request.user, period, reference, privacy, signature,
        logo_path=static_root / "pixelvault-logo.webp",
        mascot_path=static_root / "mascot-raccoon.webp",
    )
    response = HttpResponse(buf.getvalue(), content_type="image/png")
    response["Content-Disposition"] = f'attachment; filename="pixelvault-{period}-{reference.isoformat()}.png"'
    return response


@login_required
@require_GET
def report_pdf(request):
    period, reference, privacy, signature = _report_args(request)
    buf, data = build_pdf(request.user, period, reference, privacy, signature)
    response = HttpResponse(buf.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="pixelvault-{period}-{reference.isoformat()}-report.pdf"'
    return response


@login_required
@require_GET
def api_health(request):
    return JsonResponse({"ok": True, "backend": "django", "version": django_settings.PIXELVAULT_VERSION, "database": "sqlite", "user": request.user.username})
