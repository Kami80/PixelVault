from calendar import monthrange
from datetime import date, timedelta, time
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from workspace.models import Project, Task


BG = "#0c0919"
PANEL = "#17122f"
PINK = "#ff4aa2"
CYAN = "#23d9ff"
LIME = "#8cff40"
YELLOW = "#ffd23f"
TEXT = "#f7f1ff"
MUTED = "#aaa2c3"


def report_range(period: str, reference: date, week_start: str = "monday"):
    period = period if period in {"daily", "weekly", "monthly"} else "daily"
    if period == "daily":
        return reference, reference, reference.strftime("%d %b %Y")
    if period == "weekly":
        offset = reference.weekday() if week_start != "sunday" else (reference.weekday() + 1) % 7
        start = reference - timedelta(days=offset)
        end = start + timedelta(days=6)
        return start, end, f"{start.strftime('%d %b')} — {end.strftime('%d %b %Y')}"
    start = reference.replace(day=1)
    end = reference.replace(day=monthrange(reference.year, reference.month)[1])
    return start, end, reference.strftime("%B %Y")


def get_report_data(user, period="daily", reference=None, privacy="full", signature=""):
    reference = reference or timezone.localdate()
    settings_obj = getattr(user, "pixelvault_settings", None)
    week_start = settings_obj.week_start if settings_obj else "monday"
    start, end, label = report_range(period, reference, week_start)
    all_tasks = Task.objects.filter(owner=user).select_related("project")
    in_period = all_tasks.filter(scheduled_date__range=(start, end)) | all_tasks.filter(completed_on__range=(start, end))
    tasks = list(in_period.distinct())
    completed = [t for t in tasks if t.status == "done" and t.completed_on and start <= t.completed_on <= end]
    scheduled = [t for t in tasks if t.scheduled_date and start <= t.scheduled_date <= end]
    planned_minutes = sum(t.duration_minutes or 0 for t in scheduled)
    done_minutes = sum(t.duration_minutes or 0 for t in completed)
    active_projects = {}
    for t in completed:
        name = t.project.title if t.project else "Independent"
        active_projects[name] = active_projects.get(name, 0) + 1
    top_projects = sorted(active_projects.items(), key=lambda x: (-x[1], x[0]))[:6]
    overdue = all_tasks.exclude(status="done").filter(due_date__lt=timezone.localdate()).count()
    sig = signature or (settings_obj.signature if settings_obj else "") or (settings_obj.social_handle if settings_obj else "") or (settings_obj.workspace_name if settings_obj else "PixelVault")
    return {
        "period": period,
        "reference": reference,
        "start": start,
        "end": end,
        "label": label,
        "privacy": privacy,
        "signature": sig,
        "tasks": tasks,
        "completed": completed,
        "scheduled": scheduled,
        "planned_minutes": planned_minutes,
        "done_minutes": done_minutes,
        "top_projects": top_projects,
        "overdue": overdue,
        "completion_rate": round((len(completed) / len(scheduled) * 100) if scheduled else 0),
    }


def _public_title(task, privacy):
    if privacy == "public":
        return f"Completed {task.task_type.replace('-', ' ')} task"
    if privacy == "showcase":
        return task.title if task.priority == "high" or task.pinned else f"Progress on {task.project.title if task.project else 'independent work'}"
    return task.title


def _font(size=32, bold=False):
    candidates = [
        "DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "consolab.ttf" if bold else "consola.ttf",
        "courbd.ttf" if bold else "cour.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def build_social_png(user, period, reference, privacy, signature, logo_path=None, mascot_path=None):
    data = get_report_data(user, period, reference, privacy, signature)
    w, h = 1080, 1350
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)
    # Pixel frame
    d.rounded_rectangle((44, 44, w - 44, h - 44), radius=18, fill=PANEL, outline=CYAN, width=4)
    d.rectangle((44, 44, w - 44, 58), fill=PINK)
    d.rectangle((44, h - 58, w - 44, h - 44), fill=LIME)
    title_font = _font(68, True)
    h2 = _font(34, True)
    body = _font(27, False)
    small = _font(22, False)
    d.text((76, 88), "PIXELVAULT", font=title_font, fill=PINK)
    d.text((78, 168), f"{data['period'].upper()} REPORT · {data['label'].upper()}", font=small, fill=CYAN)

    # Stats
    stats = [
        ("TASKS DONE", str(len(data["completed"])), PINK),
        ("FOCUS", f"{data['done_minutes']/60:.1f}h", CYAN),
        ("COMPLETION", f"{data['completion_rate']}%", LIME),
        ("PROJECTS", str(len(data["top_projects"])), YELLOW),
    ]
    x0, y0 = 76, 235
    card_w, gap = 215, 22
    for idx, (label, value, color) in enumerate(stats):
        x = x0 + idx * (card_w + gap)
        d.rounded_rectangle((x, y0, x + card_w, y0 + 170), radius=12, fill="#0f0c23", outline=color, width=3)
        d.text((x + 18, y0 + 22), label, font=small, fill=MUTED)
        d.text((x + 18, y0 + 78), value, font=h2, fill=color)

    d.text((76, 455), "TOP COMPLETED", font=h2, fill=TEXT)
    y = 510
    completed = data["completed"][:7]
    if not completed:
        d.text((80, y), "No completed tasks in this period yet.", font=body, fill=MUTED)
        y += 58
    for i, task in enumerate(completed, 1):
        d.rounded_rectangle((76, y, 1004, y + 86), radius=10, fill="#100c27", outline="#342958", width=2)
        d.text((96, y + 15), f"{i:02d}", font=h2, fill=LIME)
        title = _public_title(task, privacy)
        if len(title) > 47:
            title = title[:44] + "…"
        d.text((166, y + 17), title, font=body, fill=TEXT)
        project = task.project.title if task.project else "Independent"
        if privacy == "public":
            project = "Private project"
        d.text((166, y + 54), project[:52], font=small, fill=MUTED)
        y += 102

    d.text((76, min(y + 20, 1120)), "PROJECT MOMENTUM", font=h2, fill=TEXT)
    py = min(y + 72, 1170)
    for name, count in data["top_projects"][:4]:
        shown = "Private project" if privacy == "public" else name
        d.text((80, py), shown[:34], font=small, fill=MUTED)
        bar_x = 430
        d.rectangle((bar_x, py + 4, 900, py + 24), fill="#27203f")
        max_count = max([c for _, c in data["top_projects"]] or [1])
        d.rectangle((bar_x, py + 4, bar_x + int(470 * count / max_count), py + 24), fill=CYAN)
        d.text((925, py - 2), str(count), font=small, fill=LIME)
        py += 42

    d.text((76, 1265), f"{data['signature']}  ·  KEEP BUILDING!", font=small, fill=PINK)
    if logo_path and Path(logo_path).exists():
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((310, 150), Image.Resampling.LANCZOS)
            im.paste(logo, (w - logo.width - 68, 72), logo)
        except Exception:
            pass
    if mascot_path and Path(mascot_path).exists():
        try:
            mascot = Image.open(mascot_path).convert("RGBA")
            mascot.thumbnail((235, 235), Image.Resampling.LANCZOS)
            im.paste(mascot, (w - mascot.width - 60, h - mascot.height - 80), mascot)
        except Exception:
            pass
    out = BytesIO()
    im.save(out, format="PNG", optimize=True)
    out.seek(0)
    return out, data


def build_pdf(user, period, reference, privacy, signature):
    data = get_report_data(user, period, reference, privacy, signature)
    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm,
                            title=f"PixelVault {period.title()} Report")
    styles = getSampleStyleSheet()
    title = ParagraphStyle("pv-title", parent=styles["Title"], fontName="Courier-Bold", fontSize=26, leading=30, textColor=colors.HexColor(PINK), spaceAfter=6)
    subtitle = ParagraphStyle("pv-subtitle", parent=styles["Normal"], fontName="Courier", fontSize=10, textColor=colors.HexColor(CYAN), spaceAfter=16)
    section = ParagraphStyle("pv-section", parent=styles["Heading2"], fontName="Courier-Bold", fontSize=14, textColor=colors.HexColor(LIME), spaceBefore=12, spaceAfter=8)
    body = ParagraphStyle("pv-body", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.5, leading=14, textColor=colors.HexColor("#222233"))
    small = ParagraphStyle("pv-small", parent=body, fontSize=8.5, textColor=colors.HexColor("#55556b"))
    story = [
        Paragraph("PIXELVAULT", title),
        Paragraph(xml_escape(f"{period.upper()} PRODUCTIVITY REPORT · {data['label']} · {data['signature']}"), subtitle),
        Paragraph("EXECUTIVE SUMMARY", section),
    ]
    summary = [
        ["Completed tasks", str(len(data["completed"]))],
        ["Scheduled tasks", str(len(data["scheduled"]))],
        ["Completion rate", f"{data['completion_rate']}%"],
        ["Completed focus time", f"{data['done_minutes']/60:.1f} hours"],
        ["Planned time", f"{data['planned_minutes']/60:.1f} hours"],
        ["Current overdue tasks", str(data["overdue"])],
    ]
    t = Table(summary, colWidths=[90*mm, 55*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#f5f1ff")),
        ("TEXTCOLOR", (0,0), (0,-1), colors.HexColor("#4e3d75")),
        ("TEXTCOLOR", (1,0), (1,-1), colors.HexColor("#111122")),
        ("FONTNAME", (0,0), (-1,-1), "Courier"),
        ("FONTNAME", (1,0), (1,-1), "Courier-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#d9cfff")),
        ("BOX", (0,0), (-1,-1), 1, colors.HexColor(CYAN)),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]))
    story += [t, Spacer(1, 6*mm), Paragraph("COMPLETED WORK", section)]
    if data["completed"]:
        rows = [["Task", "Project", "Date", "Time"]]
        for task in data["completed"]:
            project = task.project.title if task.project else "Independent"
            if privacy == "public":
                project = "Private project"
            rows.append([
                Paragraph(xml_escape(_public_title(task, privacy)), small),
                Paragraph(xml_escape(project), small),
                task.completed_on.isoformat() if task.completed_on else "—",
                f"{task.duration_minutes}m",
            ])
        tbl = Table(rows, repeatRows=1, colWidths=[76*mm, 45*mm, 28*mm, 18*mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor(PANEL)),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTNAME", (0,0), (-1,0), "Courier-Bold"),
            ("FONTSIZE", (0,0), (-1,0), 8),
            ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#cfc7dc")),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#faf8ff")]),
            ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
            ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ]))
        story.append(tbl)
    else:
        story.append(Paragraph("No completed tasks were recorded in this report period.", body))

    story += [Spacer(1, 5*mm), Paragraph("PROJECT BREAKDOWN", section)]
    if data["top_projects"]:
        for name, count in data["top_projects"]:
            shown = "Private project" if privacy == "public" else name
            story.append(Paragraph(f"<b>{xml_escape(shown)}</b> — {count} completed task{'s' if count != 1 else ''}", body))
    else:
        story.append(Paragraph("No project activity was recorded.", body))

    story += [PageBreak(), Paragraph("PLANNER REVIEW", title), Paragraph(data["label"], subtitle)]
    for task in sorted(data["scheduled"], key=lambda x: (x.scheduled_date or data["end"], x.start_time or time.max)):
        project = task.project.title if task.project else "Independent"
        if privacy == "public": project = "Private project"
        time_label = task.start_time.strftime("%H:%M") if task.start_time else "Anytime"
        story.append(Paragraph(f"<b>{task.scheduled_date or 'Unscheduled'} · {time_label}</b> — {xml_escape(_public_title(task, privacy))}", body))
        story.append(Paragraph(xml_escape(f"{project} · {task.priority} priority · {task.duration_minutes} min · {task.status}"), small))
        story.append(Spacer(1, 2.2*mm))

    story += [Spacer(1, 4*mm), Paragraph("NEXT ACTIONS", section)]
    next_tasks = Task.objects.filter(owner=user).exclude(status="done").select_related("project").order_by("due_date", "-priority", "title")[:30]
    for idx, task in enumerate(next_tasks, 1):
        project = task.project.title if task.project else "Independent"
        if privacy == "public": project = "Private project"
        due = task.due_date.isoformat() if task.due_date else "unscheduled"
        story.append(Paragraph(f"{idx}. <b>{xml_escape(_public_title(task, privacy))}</b> — {xml_escape(project)} · due {due}", body))

    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor(PINK))
        canvas.setLineWidth(1.2)
        canvas.line(18*mm, 13*mm, 192*mm, 13*mm)
        canvas.setFillColor(colors.HexColor("#5b5272"))
        canvas.setFont("Courier", 7.5)
        canvas.drawString(18*mm, 8*mm, f"{data['signature']} · PIXELVAULT")
        canvas.drawRightString(192*mm, 8*mm, f"PAGE {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    out.seek(0)
    return out, data
