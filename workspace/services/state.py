import re
from datetime import date, datetime, time
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime, parse_time

from workspace.models import Annotation, Idea, Project, Skill, Task, UserSettings

ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _date(v, default=None):
    if isinstance(v, date):
        return v
    if not v:
        return default
    return parse_date(str(v)[:10]) or default


def _time(v):
    if isinstance(v, time):
        return v
    if not v:
        return None
    return parse_time(str(v))


def _datetime(v):
    if isinstance(v, datetime):
        return v
    if not v:
        return timezone.now()
    dt = parse_datetime(str(v))
    if dt is None:
        d = _date(v)
        if d:
            dt = datetime.combine(d, time(12, 0))
    if dt and timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt or timezone.now()


def _list(v):
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if not v:
        return []
    return [x.strip() for x in str(v).split(",") if x.strip()]


def _bool(v):
    if isinstance(v, bool):
        return v
    return str(v).lower() in {"1", "true", "yes", "on"}


def _int(v, default=0, minimum=None, maximum=None):
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = default
    if minimum is not None:
        n = max(minimum, n)
    if maximum is not None:
        n = min(maximum, n)
    return n


def _safe_id(v, prefix):
    raw = str(v or "")
    if ID_RE.fullmatch(raw):
        return raw
    from workspace.models import make_id
    return make_id(prefix)


def ensure_settings(user):
    obj, _ = UserSettings.objects.get_or_create(user=user)
    return obj


def serialize_settings(s: UserSettings):
    return {
        "signature": s.signature,
        "plannerView": s.planner_view,
        "plannerAnchor": s.planner_anchor.isoformat() if s.planner_anchor else timezone.localdate().isoformat(),
        "skillSelected": s.skill_selected or None,
        "theme": s.theme,
        "accent": s.accent,
        "density": s.density,
        "textSize": s.text_size,
        "reduceMotion": s.reduce_motion,
        "showGrid": s.show_grid,
        "showMascots": s.show_mascots,
        "highContrast": s.high_contrast,
        "largeTargets": s.large_targets,
        "displayName": s.display_name,
        "role": s.role,
        "workspaceName": s.workspace_name,
        "socialHandle": s.social_handle,
        "bio": s.bio,
        "avatar": s.avatar,
        "landingPage": s.landing_page,
        "plannerDefaultView": s.planner_default_view,
        "weekStart": s.week_start,
        "workdayStart": s.workday_start,
        "workdayEnd": s.workday_end,
        "defaultTaskDuration": s.default_task_duration,
        "plannerSnapMinutes": s.planner_snap_minutes,
        "plannerHourPx": s.planner_hour_px,
        "defaultHighlight": s.default_highlight,
        "showHighlights": s.show_highlights,
        "confirmDeletes": s.confirm_deletes,
        "workspaceRoot": s.workspace_root,
    }


def serialize_project(p: Project):
    return {
        "id": p.id,
        "title": p.title,
        "description": p.description,
        "tags": p.tags or [],
        "status": p.status,
        "pathHint": p.local_path,
        "launchUrl": p.launch_url,
        "repositoryUrl": p.repository_url,
        "githubPagesUrl": p.github_pages_url,
        "techStack": p.tech_stack or [],
        "isWeb": p.is_web,
        "pinned": p.pinned,
        "progress": p.progress,
        "notes": p.notes,
        "dueDate": p.target_date.isoformat() if p.target_date else "",
        "goal": p.goal,
        "milestone": p.next_milestone,
        "created": p.created_on.isoformat(),
        "updated": p.updated_on.isoformat(),
    }


def serialize_idea(i: Idea):
    return {
        "id": i.id,
        "title": i.title,
        "description": i.description,
        "contentType": i.content_type,
        "content": i.content,
        "status": i.status,
        "priority": i.priority,
        "goal": i.goal,
        "audience": i.audience,
        "sourceUrl": i.source_url,
        "liveSiteUrl": i.live_site_url,
        "tags": i.tags or [],
        "projectId": i.project_id or "",
        "nextAction": i.next_action,
        "pinned": i.pinned,
        "created": i.created_on.isoformat(),
        "updated": i.updated_on.isoformat(),
    }


def serialize_task(t: Task):
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "projectId": t.project_id or "",
        "status": t.status,
        "priority": t.priority,
        "taskType": t.task_type,
        "energy": t.energy,
        "scheduledDate": t.scheduled_date.isoformat() if t.scheduled_date else "",
        "dueDate": t.due_date.isoformat() if t.due_date else "",
        "time": t.start_time.strftime("%H:%M") if t.start_time else "",
        "duration": t.duration_minutes,
        "recurrence": t.recurrence,
        "dependsOn": t.depends_on_id or "",
        "subtasks": t.subtasks or [],
        "tags": t.tags or [],
        "notes": t.notes,
        "pinned": t.pinned,
        "completedAt": t.completed_on.isoformat() if t.completed_on else "",
        "created": t.created_on.isoformat(),
        "updated": t.updated_on.isoformat(),
    }


def serialize_skill(s: Skill):
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "category": s.category,
        "version": s.version,
        "sourceUrl": s.source_url,
        "tags": s.tags or [],
        "agents": s.agents or [],
        "useCases": s.use_cases or [],
        "filename": s.filename,
        "content": s.content,
        "attachedFile": s.attached_file.url if s.attached_file else "",
        "pinned": s.pinned,
        "created": s.created_on.isoformat(),
        "updated": s.updated_on.isoformat(),
    }


def serialize_annotation(a: Annotation):
    return {
        "id": a.id,
        "quote": a.selected_text,
        "page": a.page_key,
        "prefix": a.prefix,
        "suffix": a.suffix,
        "color": a.color,
        "comment": a.comment,
        "created": a.created_at.isoformat(),
    }


def state_for_user(user):
    settings = ensure_settings(user)
    return {
        "version": 4,
        "settings": serialize_settings(settings),
        "ideas": [serialize_idea(x) for x in Idea.objects.filter(owner=user).select_related("project")],
        "projects": [serialize_project(x) for x in Project.objects.filter(owner=user)],
        "tasks": [serialize_task(x) for x in Task.objects.filter(owner=user).select_related("project", "depends_on")],
        "skills": [serialize_skill(x) for x in Skill.objects.filter(owner=user)],
        "annotations": [serialize_annotation(x) for x in Annotation.objects.filter(owner=user)],
    }


def _owned_upsert(model, user, object_id, defaults):
    conflict = model.objects.filter(pk=object_id).exclude(owner=user).exists()
    if conflict:
        raise ValidationError(f"Identifier {object_id!r} is already owned by another account.")
    obj, _ = model.objects.update_or_create(pk=object_id, owner=user, defaults=defaults)
    return obj


@transaction.atomic
def save_workspace_state(user, payload: dict[str, Any]):
    if not isinstance(payload, dict):
        raise ValidationError("Workspace state must be a JSON object.")
    today = timezone.localdate()
    s = ensure_settings(user)
    incoming = payload.get("settings") or {}
    mapping = {
        "display_name": ("displayName", str),
        "role": ("role", str),
        "workspace_name": ("workspaceName", str),
        "social_handle": ("socialHandle", str),
        "bio": ("bio", str),
        "avatar": ("avatar", str),
        "theme": ("theme", str),
        "accent": ("accent", str),
        "density": ("density", str),
        "text_size": ("textSize", str),
        "landing_page": ("landingPage", str),
        "planner_default_view": ("plannerDefaultView", str),
        "planner_view": ("plannerView", str),
        "week_start": ("weekStart", str),
        "default_highlight": ("defaultHighlight", str),
        "signature": ("signature", str),
        "skill_selected": ("skillSelected", str),
        "workspace_root": ("workspaceRoot", str),
    }
    for field, (key, caster) in mapping.items():
        if key in incoming and incoming[key] is not None:
            setattr(s, field, caster(incoming[key])[:1024])
    bool_map = {
        "reduce_motion": "reduceMotion", "show_grid": "showGrid", "show_mascots": "showMascots",
        "confirm_deletes": "confirmDeletes", "high_contrast": "highContrast", "large_targets": "largeTargets",
        "show_highlights": "showHighlights",
    }
    for field, key in bool_map.items():
        if key in incoming:
            setattr(s, field, _bool(incoming[key]))
    if "plannerAnchor" in incoming:
        s.planner_anchor = _date(incoming.get("plannerAnchor"), today)
    if "workdayStart" in incoming:
        s.workday_start = _int(incoming.get("workdayStart"), 7, 0, 23)
    if "workdayEnd" in incoming:
        s.workday_end = _int(incoming.get("workdayEnd"), 22, 1, 24)
    if s.workday_end <= s.workday_start:
        s.workday_end = min(24, s.workday_start + 1)
    if "defaultTaskDuration" in incoming:
        s.default_task_duration = _int(incoming.get("defaultTaskDuration"), 45, 5, 1440)
    if "plannerSnapMinutes" in incoming:
        snap = _int(incoming.get("plannerSnapMinutes"), 15, 15, 60)
        s.planner_snap_minutes = snap if snap in {15, 30, 60} else 15
    if "plannerHourPx" in incoming:
        s.planner_hour_px = _int(incoming.get("plannerHourPx"), 96, 64, 144)
    s.full_clean()
    s.save()

    # Projects must be materialized before ideas/tasks can reference them.
    project_ids = set()
    for raw in payload.get("projects") or []:
        oid = _safe_id(raw.get("id"), "project")
        project_ids.add(oid)
        _owned_upsert(Project, user, oid, {
            "title": str(raw.get("title") or "Untitled Project")[:180],
            "description": str(raw.get("description") or ""),
            "tags": _list(raw.get("tags")),
            "status": str(raw.get("status") or "active")[:20],
            "progress": _int(raw.get("progress"), 0, 0, 100),
            "local_path": str(raw.get("pathHint") or "")[:1024],
            "launch_url": str(raw.get("launchUrl") or "")[:1000],
            "repository_url": str(raw.get("repositoryUrl") or "")[:1000],
            "github_pages_url": str(raw.get("githubPagesUrl") or "")[:1000],
            "tech_stack": _list(raw.get("techStack")),
            "is_web": _bool(raw.get("isWeb")),
            "target_date": _date(raw.get("dueDate")),
            "goal": str(raw.get("goal") or ""),
            "next_milestone": str(raw.get("milestone") or "")[:500],
            "notes": str(raw.get("notes") or ""),
            "pinned": _bool(raw.get("pinned")),
            "created_on": _date(raw.get("created"), today),
            "updated_on": _date(raw.get("updated"), today),
        })
    Project.objects.filter(owner=user).exclude(pk__in=project_ids).delete()
    owned_projects = {p.id: p for p in Project.objects.filter(owner=user)}

    idea_ids = set()
    for raw in payload.get("ideas") or []:
        oid = _safe_id(raw.get("id"), "idea")
        idea_ids.add(oid)
        pid = str(raw.get("projectId") or "")
        _owned_upsert(Idea, user, oid, {
            "title": str(raw.get("title") or "Untitled Idea")[:180],
            "description": str(raw.get("description") or ""),
            "content_type": str(raw.get("contentType") or "note")[:20],
            "content": str(raw.get("content") or ""),
            "status": str(raw.get("status") or "inbox")[:20],
            "priority": str(raw.get("priority") or "medium")[:12],
            "goal": str(raw.get("goal") or ""),
            "audience": str(raw.get("audience") or "")[:180],
            "source_url": str(raw.get("sourceUrl") or "")[:1000],
            "live_site_url": str(raw.get("liveSiteUrl") or "")[:1000],
            "tags": _list(raw.get("tags")),
            "project": owned_projects.get(pid),
            "next_action": str(raw.get("nextAction") or "")[:500],
            "pinned": _bool(raw.get("pinned")),
            "created_on": _date(raw.get("created"), today),
            "updated_on": _date(raw.get("updated"), today),
        })
    Idea.objects.filter(owner=user).exclude(pk__in=idea_ids).delete()

    # First pass for tasks: omit dependencies until every task exists.
    task_ids = set()
    raw_tasks = payload.get("tasks") or []
    for raw in raw_tasks:
        oid = _safe_id(raw.get("id"), "task")
        task_ids.add(oid)
        pid = str(raw.get("projectId") or "")
        status = str(raw.get("status") or "todo")[:12]
        completed = _date(raw.get("completedAt"))
        if status == "done" and not completed:
            completed = today
        _owned_upsert(Task, user, oid, {
            "title": str(raw.get("title") or "Untitled Task")[:220],
            "description": str(raw.get("description") or ""),
            "project": owned_projects.get(pid),
            "status": status,
            "priority": str(raw.get("priority") or "medium")[:12],
            "task_type": str(raw.get("taskType") or "development")[:40],
            "energy": str(raw.get("energy") or "medium")[:12],
            "scheduled_date": _date(raw.get("scheduledDate")),
            "due_date": _date(raw.get("dueDate")),
            "start_time": _time(raw.get("time")),
            "duration_minutes": _int(raw.get("duration"), s.default_task_duration, 0, 1440),
            "recurrence": str(raw.get("recurrence") or "none")[:12],
            "depends_on": None,
            "subtasks": _list(raw.get("subtasks")),
            "tags": _list(raw.get("tags")),
            "notes": str(raw.get("notes") or ""),
            "pinned": _bool(raw.get("pinned")),
            "completed_on": completed,
            "created_on": _date(raw.get("created"), today),
            "updated_on": _date(raw.get("updated"), today),
        })
    Task.objects.filter(owner=user).exclude(pk__in=task_ids).delete()
    owned_tasks = {t.id: t for t in Task.objects.filter(owner=user)}
    for raw in raw_tasks:
        oid = str(raw.get("id") or "")
        dep = str(raw.get("dependsOn") or "")
        if oid in owned_tasks:
            target = owned_tasks.get(dep)
            if target and target.id != oid:
                Task.objects.filter(owner=user, pk=oid).update(depends_on=target)

    skill_ids = set()
    for raw in payload.get("skills") or []:
        oid = _safe_id(raw.get("id"), "skill")
        skill_ids.add(oid)
        existing = Skill.objects.filter(owner=user, pk=oid).first()
        attached = existing.attached_file if existing else ""
        _owned_upsert(Skill, user, oid, {
            "name": str(raw.get("name") or "Untitled Skill")[:180],
            "description": str(raw.get("description") or ""),
            "category": str(raw.get("category") or "General")[:100],
            "version": str(raw.get("version") or "1.0.0")[:40],
            "source_url": str(raw.get("sourceUrl") or "")[:1000],
            "tags": _list(raw.get("tags")),
            "agents": _list(raw.get("agents")),
            "use_cases": _list(raw.get("useCases")),
            "filename": str(raw.get("filename") or "skill.md")[:255],
            "content": str(raw.get("content") or ""),
            "attached_file": attached,
            "pinned": _bool(raw.get("pinned")),
            "created_on": _date(raw.get("created"), today),
            "updated_on": _date(raw.get("updated"), today),
        })
    Skill.objects.filter(owner=user).exclude(pk__in=skill_ids).delete()

    annotation_ids = set()
    for raw in payload.get("annotations") or []:
        oid = _safe_id(raw.get("id"), "ann")
        annotation_ids.add(oid)
        _owned_upsert(Annotation, user, oid, {
            "page_key": str(raw.get("page") or "home")[:40],
            "selected_text": str(raw.get("quote") or ""),
            "prefix": str(raw.get("prefix") or ""),
            "suffix": str(raw.get("suffix") or ""),
            "color": str(raw.get("color") or s.default_highlight)[:16],
            "comment": str(raw.get("comment") or ""),
            "created_at": _datetime(raw.get("created")),
        })
    Annotation.objects.filter(owner=user).exclude(pk__in=annotation_ids).delete()

    return state_for_user(user)
