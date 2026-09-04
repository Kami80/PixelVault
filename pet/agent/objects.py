import re
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from workspace.models import Activity, Idea, Project, Skill, Task

from ..models import PetConversation


OBJECT_REFERENCE = re.compile(
    r"\[(project|idea|task|skill):([A-Za-z0-9_-]{1,128})\]",
    re.IGNORECASE,
)
OBJECT_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
POLITE_PREFIX = re.compile(
    r"^\s*(?:(?:hey|hi|okay|ok)[,!\s]+)?(?:please\s+)?"
    r"(?:(?:can|could|would|will)\s+you\s+|"
    r"i\s+(?:want|need)\s+(?:you\s+)?to\s+|"
    r"i(?:'d|\s+would)\s+like\s+(?:you\s+)?to\s+)?(?:please\s+)?",
    re.IGNORECASE,
)
OBJECT_MODELS = {
    "project": (Project, "title"),
    "idea": (Idea, "title"),
    "task": (Task, "title"),
    "skill": (Skill, "name"),
}
TYPE_ALIASES = {
    "project": "project",
    "projects": "project",
    "idea": "idea",
    "ideas": "idea",
    "task": "task",
    "tasks": "task",
    "todo": "task",
    "todos": "task",
    "to-do": "task",
    "to-dos": "task",
    "skill": "skill",
    "skills": "skill",
}
REFERENCE_WORDS = {"", "this", "that", "it", "this one", "that one", "the one"}


class WorkspaceObjectError(Exception):
    pass


class WorkspaceObjectNotFound(WorkspaceObjectError):
    pass


def normalize_object_type(value):
    normalized = str(value or "").lower().strip().replace(" ", "-")
    return TYPE_ALIASES.get(normalized, "")


def get_owned_object(user, object_type, object_id):
    normalized_type = normalize_object_type(object_type)
    if normalized_type not in OBJECT_MODELS or not OBJECT_ID.fullmatch(str(object_id or "")):
        raise WorkspaceObjectNotFound("That workspace object does not exist.")
    model, _ = OBJECT_MODELS[normalized_type]
    try:
        return normalized_type, model.objects.get(owner=user, pk=object_id)
    except model.DoesNotExist as exc:
        raise WorkspaceObjectNotFound("That workspace object does not exist.") from exc


def _object_actions(object_type, item):
    pin_action = {
        "id": "unpin" if item.pinned else "pin",
        "label": "UNPIN" if item.pinned else "PIN",
    }
    if object_type == "task":
        actions = []
        if item.status == "todo":
            actions.append({"id": "start", "label": "START"})
        if item.status != "done":
            actions.append({"id": "complete", "label": "DONE", "tone": "success"})
        else:
            actions.append({"id": "reopen", "label": "REOPEN"})
        return [*actions, pin_action]
    if object_type == "idea":
        next_status = {
            "inbox": ("exploring", "EXPLORE"),
            "exploring": ("ready", "READY"),
            "ready": ("building", "BUILD"),
            "building": ("ready", "READY"),
        }.get(item.status)
        actions = []
        if next_status:
            actions.append({"id": "set_status", "value": next_status[0], "label": next_status[1]})
        actions.append({"id": "convert_project", "label": "PROJECT"})
        actions.append(pin_action)
        return actions
    if object_type == "project":
        if item.status == "active":
            return [
                {"id": "pause", "label": "PAUSE"},
                {"id": "complete", "label": "DONE", "tone": "success"},
                pin_action,
            ]
        return [
            {"id": "activate", "label": "ACTIVATE"},
            pin_action,
        ]
    return [pin_action]


def serialize_workspace_object(object_type, item):
    label_field = OBJECT_MODELS[object_type][1]
    metadata = []
    status = str(getattr(item, "status", "") or "")
    if status:
        metadata.append(status.upper())
    if object_type in {"task", "idea"}:
        metadata.append(str(item.priority or "medium").upper())
    if object_type == "task":
        if item.due_date:
            metadata.append(f"DUE {item.due_date.isoformat()}")
        if item.project_id:
            metadata.append(item.project.title)
    elif object_type == "idea" and item.project_id:
        metadata.append(item.project.title)
    elif object_type == "project":
        metadata.append(f"{item.progress}%")
        if item.target_date:
            metadata.append(f"TARGET {item.target_date.isoformat()}")
    elif object_type == "skill":
        metadata.extend([item.category or "General", f"v{item.version or '1.0.0'}"])
    return {
        "type": object_type,
        "id": str(item.pk),
        "title": str(getattr(item, label_field, item.pk)),
        "status": status,
        "meta": " · ".join(metadata),
        "pinned": bool(item.pinned),
        "actions": _object_actions(object_type, item),
    }


def _touch(item, fields):
    if hasattr(item, "updated_on"):
        item.updated_on = timezone.localdate()
        fields.append("updated_on")
    item.save(update_fields=list(dict.fromkeys(fields)))


def _audit_update(user, object_type, item, action):
    label_field = OBJECT_MODELS[object_type][1]
    Activity.objects.create(
        owner=user,
        verb="updated",
        entity_type=object_type,
        entity_id=str(item.pk)[:64],
        label=str(getattr(item, label_field))[:250],
        metadata={"source": "pet_agent", "action": action},
    )


def _parse_date(value):
    lowered = str(value or "").strip().lower()
    if lowered == "today":
        return timezone.localdate()
    if lowered == "tomorrow":
        return timezone.localdate() + timedelta(days=1)
    try:
        return datetime.strptime(lowered, "%Y-%m-%d").date()
    except ValueError as exc:
        raise WorkspaceObjectError("Use today, tomorrow, or a date like 2026-09-15.") from exc


def _result_message(object_type, item, action, value=""):
    label_field = OBJECT_MODELS[object_type][1]
    title = str(getattr(item, label_field))
    messages = {
        "pin": f"Pinned “{title}.”",
        "unpin": f"Unpinned “{title}.”",
        "start": f"Started “{title}.”",
        "complete": f"Marked “{title}” done.",
        "reopen": f"Reopened “{title}.”",
        "pause": f"Paused “{title}.”",
        "activate": f"Activated “{title}.”",
        "set_status": f"Moved “{title}” to {value}.",
        "set_priority": f"Set “{title}” to {value} priority.",
        "set_due": f"Scheduled “{title}” for {value}.",
        "set_progress": f"Updated “{title}” to {value}% progress.",
        "rename": f"Renamed it to “{title}.”",
    }
    return messages.get(action, f"Updated “{title}.”")


@transaction.atomic
def perform_object_action(user, object_type, object_id, action, value=""):
    object_type, item = get_owned_object(user, object_type, object_id)
    action = str(action or "").strip().lower()
    value = str(value or "").strip()
    if action in {"pin", "unpin"}:
        item.pinned = action == "pin"
        _touch(item, ["pinned"])
    elif action == "rename":
        label_field = OBJECT_MODELS[object_type][1]
        max_length = item._meta.get_field(label_field).max_length
        new_title = re.sub(r"\s+", " ", value).strip(" \t\r\n'\"`")
        if not new_title:
            raise WorkspaceObjectError("Give me a new name first.")
        setattr(item, label_field, new_title[:max_length])
        _touch(item, [label_field])
    elif action == "start" and object_type == "task":
        item.status = "doing"
        item.completed_on = None
        _touch(item, ["status", "completed_on"])
    elif action == "complete" and object_type == "task":
        item.status = "done"
        item.completed_on = timezone.localdate()
        _touch(item, ["status", "completed_on"])
    elif action == "reopen" and object_type == "task":
        item.status = "todo"
        item.completed_on = None
        _touch(item, ["status", "completed_on"])
    elif action == "pause" and object_type == "project":
        item.status = "paused"
        _touch(item, ["status"])
    elif action == "activate" and object_type == "project":
        item.status = "active"
        _touch(item, ["status"])
    elif action == "complete" and object_type == "project":
        item.status = "done"
        item.progress = 100
        _touch(item, ["status", "progress"])
    elif action == "set_status":
        choices = {choice for choice, _label in item._meta.get_field("status").choices}
        normalized_value = value.lower()
        if normalized_value not in choices:
            raise WorkspaceObjectError(
                f"{object_type.title()} status must be one of: {', '.join(sorted(choices))}."
            )
        item.status = normalized_value
        fields = ["status"]
        if object_type == "task":
            item.completed_on = timezone.localdate() if normalized_value == "done" else None
            fields.append("completed_on")
        if object_type == "project" and normalized_value == "done":
            item.progress = 100
            fields.append("progress")
        _touch(item, fields)
        value = normalized_value
    elif action == "set_priority" and object_type in {"task", "idea"}:
        normalized_value = value.lower()
        if normalized_value not in {"high", "medium", "low"}:
            raise WorkspaceObjectError("Priority must be high, medium, or low.")
        item.priority = normalized_value
        _touch(item, ["priority"])
        value = normalized_value
    elif action == "set_due" and object_type == "task":
        item.due_date = _parse_date(value)
        _touch(item, ["due_date"])
        value = item.due_date.isoformat()
    elif action == "set_progress" and object_type == "project":
        try:
            progress = int(value.rstrip("%"))
        except ValueError as exc:
            raise WorkspaceObjectError("Progress must be a number from 0 to 100.") from exc
        if not 0 <= progress <= 100:
            raise WorkspaceObjectError("Progress must be a number from 0 to 100.")
        item.progress = progress
        if progress == 100:
            item.status = "done"
        elif item.status == "done":
            item.status = "active"
        _touch(item, ["progress", "status"])
        value = str(progress)
    elif action == "convert_project" and object_type == "idea":
        project = item.project
        project_created = False
        if project is None:
            project = Project.objects.filter(owner=user, title__iexact=item.title).first()
        if project is None:
            project = Project.objects.create(
                owner=user,
                title=item.title,
                description=item.description or item.content,
                goal=item.goal,
                tags=item.tags,
                status="active",
            )
            project_created = True
        item.project = project
        item.status = "building"
        _touch(item, ["project", "status"])
        if project_created:
            Activity.objects.create(
                owner=user,
                verb="created",
                entity_type="project",
                entity_id=str(project.pk)[:64],
                label=project.title[:250],
                metadata={"source": "pet_agent", "action": "convert_project"},
            )
        _audit_update(user, "idea", item, action)
        message = f"Turned “{item.title}” into a project. [project:{project.pk}] [idea:{item.pk}]"
        objects = [serialize_workspace_object("project", project), serialize_workspace_object("idea", item)]
        return {
            "message": message,
            "emotion": "happy",
            "objects": objects,
            "action": {"status": "updated", "objectType": "idea", "objectId": str(item.pk)},
        }
    else:
        raise WorkspaceObjectError(f"That action is not available for this {object_type}.")

    _audit_update(user, object_type, item, action)
    message = f"{_result_message(object_type, item, action, value)} [{object_type}:{item.pk}]"
    return {
        "message": message,
        "emotion": "happy",
        "objects": [serialize_workspace_object(object_type, item)],
        "action": {"status": "updated", "objectType": object_type, "objectId": str(item.pk)},
    }


def _recent_objects(user, preferred_type="", chat=None):
    conversations = PetConversation.objects.filter(pet__owner=user)
    if chat is not None:
        conversations = conversations.filter(chat=chat)
    conversations = conversations.only("pet_response")[:10]
    for conversation in conversations:
        found = []
        seen = set()
        for match in OBJECT_REFERENCE.finditer(conversation.pet_response or ""):
            object_type = match.group(1).lower()
            object_id = match.group(2)
            key = (object_type, object_id)
            if key in seen or (preferred_type and object_type != preferred_type):
                continue
            try:
                found.append(get_owned_object(user, object_type, object_id))
                seen.add(key)
            except WorkspaceObjectNotFound:
                continue
        if found:
            return found
    return []


def _extract_target(target, preferred_type=""):
    raw = re.sub(r"\s+", " ", str(target or "")).strip(" \t\r\n:;,.!?'\"`")
    detected_type = normalize_object_type(preferred_type)
    reference_hint = False

    leading = re.match(
        r"^(?:(?P<article>my|the|this|that|an?)\s+)?"
        r"(?P<kind>project|idea|task|to[ -]?do|skill)s?\b"
        r"(?:\s+(?:named|called|titled))?\s*(?P<rest>.*)$",
        raw,
        re.IGNORECASE,
    )
    if leading:
        detected_type = normalize_object_type(leading.group("kind"))
        reference_hint = (leading.group("article") or "").lower() in {"this", "that"}
        raw = leading.group("rest")
    else:
        trailing = re.match(
            r"^(?P<rest>.+?)\s+(?P<kind>project|idea|task|to[ -]?do|skill)s?$",
            raw,
            re.IGNORECASE,
        )
        if trailing:
            detected_type = normalize_object_type(trailing.group("kind"))
            raw = trailing.group("rest")

    raw = re.sub(r"^(?:my|the)\s+", "", raw, flags=re.IGNORECASE).strip(" ' \"")
    reference_hint = reference_hint or raw.lower() in REFERENCE_WORDS
    return raw, detected_type, reference_hint


def resolve_workspace_objects(user, target, preferred_type="", chat=None):
    explicit = []
    for match in OBJECT_REFERENCE.finditer(str(target or "")):
        try:
            explicit.append(get_owned_object(user, match.group(1), match.group(2)))
        except WorkspaceObjectNotFound:
            continue
    if explicit:
        return explicit

    query, object_type, reference_hint = _extract_target(target, preferred_type)
    if reference_hint:
        return _recent_objects(user, object_type, chat)
    types = [object_type] if object_type else list(OBJECT_MODELS)

    exact = []
    for candidate_type in types:
        model, label_field = OBJECT_MODELS[candidate_type]
        for item in model.objects.filter(owner=user, **{f"{label_field}__iexact": query})[:6]:
            exact.append((candidate_type, item))
    if exact:
        return exact

    partial = []
    if len(query) >= 2:
        for candidate_type in types:
            model, label_field = OBJECT_MODELS[candidate_type]
            for item in model.objects.filter(owner=user, **{f"{label_field}__icontains": query})[:6]:
                partial.append((candidate_type, item))
    return partial[:8]


def _describe_object(object_type, item):
    title = getattr(item, OBJECT_MODELS[object_type][1])
    if object_type == "task":
        details = [item.status, f"{item.priority} priority", f"{item.duration_minutes} minutes"]
        if item.due_date:
            details.append(f"due {item.due_date.isoformat()}")
        if item.project_id:
            details.append(f"project {item.project.title}")
    elif object_type == "idea":
        details = [item.status, f"{item.priority} priority"]
        if item.project_id:
            details.append(f"linked to {item.project.title}")
    elif object_type == "project":
        details = [item.status, f"{item.progress}% complete"]
        if item.target_date:
            details.append(f"target {item.target_date.isoformat()}")
        details.append(f"{item.tasks.exclude(status='done').count()} open tasks")
    else:
        details = [item.category or "General", f"version {item.version or '1.0.0'}"]
    return f"{title}: {' · '.join(details)}. [{object_type}:{item.pk}]"


def _resolution_result(user, target, action="", value="", preferred_type="", chat=None):
    matches = resolve_workspace_objects(user, target, preferred_type, chat)
    if not matches:
        type_text = f" {preferred_type}" if preferred_type else " item"
        return {
            "message": f"I couldn’t find that{type_text} in your workspace.",
            "emotion": "concerned",
            "objects": [],
            "action": {"status": "not_found", "objectType": preferred_type},
        }
    if len(matches) > 1:
        objects = [serialize_workspace_object(object_type, item) for object_type, item in matches]
        tokens = " ".join(f"[{obj['type']}:{obj['id']}]" for obj in objects)
        return {
            "message": f"I found {len(objects)} matches. Open one or use its full name so I know which you mean. {tokens}",
            "emotion": "focused",
            "objects": objects,
            "action": {"status": "ambiguous", "objectType": preferred_type},
        }
    object_type, item = matches[0]
    if not action:
        return {
            "message": _describe_object(object_type, item),
            "emotion": "focused",
            "objects": [serialize_workspace_object(object_type, item)],
            "action": {"status": "inspected", "objectType": object_type, "objectId": str(item.pk)},
        }
    try:
        return perform_object_action(user, object_type, item.pk, action, value)
    except WorkspaceObjectError as exc:
        return {
            "message": str(exc),
            "emotion": "concerned",
            "objects": [serialize_workspace_object(object_type, item)],
            "action": {"status": "unsupported", "objectType": object_type, "objectId": str(item.pk)},
        }


def _collection_result(user, object_type, filter_name=""):
    model, _ = OBJECT_MODELS[object_type]
    queryset = model.objects.filter(owner=user)
    filter_name = str(filter_name or "").lower()
    if filter_name == "pinned":
        queryset = queryset.filter(pinned=True)
    elif object_type == "task" and filter_name == "overdue":
        queryset = queryset.exclude(status="done").filter(due_date__lt=timezone.localdate())
    elif object_type == "task" and filter_name == "today":
        today = timezone.localdate()
        queryset = queryset.filter(Q(scheduled_date=today) | Q(due_date=today))
    elif filter_name:
        choices = {choice for choice, _label in model._meta.get_field("status").choices} if hasattr(model, "status") else set()
        if filter_name in choices:
            queryset = queryset.filter(status=filter_name)
    items = list(queryset[:8])
    noun = object_type if len(items) == 1 else f"{object_type}s"
    if not items:
        qualifier = f" {filter_name}" if filter_name else ""
        return {
            "message": f"You don’t have any{qualifier} {object_type}s right now.",
            "emotion": "focused",
            "objects": [],
            "action": {"status": "listed", "objectType": object_type},
        }
    objects = [serialize_workspace_object(object_type, item) for item in items]
    tokens = " ".join(f"[{obj['type']}:{obj['id']}]" for obj in objects)
    qualifier = f" {filter_name}" if filter_name else ""
    return {
        "message": f"Here {'is' if len(items) == 1 else 'are'} {len(items)}{qualifier} {noun}. {tokens}",
        "emotion": "focused",
        "objects": objects,
        "action": {"status": "listed", "objectType": object_type},
    }


def handle_object_command(user, message, chat=None):
    """Resolve explicit object commands before falling back to remote chat."""
    command = POLITE_PREFIX.sub("", re.sub(r"\s+", " ", str(message or "")).strip(), count=1)

    collection = re.fullmatch(
        r"(?:open|show|list|find|view)\s+(?:my\s+|the\s+)?"
        r"(?:(?P<filter>active|paused|done|overdue|today|todo|doing|inbox|exploring|ready|building|pinned)\s+)?"
        r"(?P<kind>projects?|ideas?|tasks?|to[ -]?dos?|skills?)\s*[.!?]?",
        command,
        re.IGNORECASE,
    )
    if collection:
        return _collection_result(
            user,
            normalize_object_type(collection.group("kind")),
            collection.group("filter") or "",
        )

    convert = re.fullmatch(
        r"(?:turn|convert|promote)\s+(?P<target>.+?)\s+(?:into|to)\s+(?:an?\s+)?project\s*[.!?]?",
        command,
        re.IGNORECASE,
    )
    if convert:
        matches = resolve_workspace_objects(user, convert.group("target"), "idea", chat)
        if not matches and _extract_target(convert.group("target"), "idea")[2]:
            return None
        return _resolution_result(
            user, convert.group("target"), "convert_project", preferred_type="idea", chat=chat
        )

    rename = re.fullmatch(r"rename\s+(?P<target>.+?)\s+to\s+(?P<value>.+)", command, re.IGNORECASE)
    if rename:
        return _resolution_result(
            user, rename.group("target"), "rename", rename.group("value"), chat=chat
        )

    priority = re.fullmatch(
        r"(?:set|make)\s+(?P<target>.+?)\s+(?:to\s+|as\s+)?(?P<value>high|medium|low)[ -]priority\s*[.!?]?",
        command,
        re.IGNORECASE,
    )
    if priority:
        return _resolution_result(
            user, priority.group("target"), "set_priority", priority.group("value"), chat=chat
        )

    due = re.fullmatch(
        r"(?:schedule|reschedule|move)\s+(?P<target>.+?)\s+(?:to|for|on)\s+"
        r"(?P<value>today|tomorrow|\d{4}-\d{2}-\d{2})\s*[.!?]?",
        command,
        re.IGNORECASE,
    )
    if due:
        return _resolution_result(
            user, due.group("target"), "set_due", due.group("value"), "task", chat
        )

    progress = re.fullmatch(
        r"(?:set|update)\s+(?P<target>.+?)\s+progress\s+(?:to|at)\s+(?P<value>\d{1,3})%?\s*[.!?]?",
        command,
        re.IGNORECASE,
    )
    if progress:
        return _resolution_result(
            user, progress.group("target"), "set_progress", progress.group("value"), "project", chat
        )

    marked = re.fullmatch(
        r"mark\s+(?P<target>.+?)\s+(?:as\s+)?"
        r"(?P<value>todo|doing|done|active|paused|inbox|exploring|ready|building)\s*[.!?]?",
        command,
        re.IGNORECASE,
    )
    if marked:
        return _resolution_result(
            user, marked.group("target"), "set_status", marked.group("value"), chat=chat
        )

    simple_patterns = (
        (r"(?:complete|finish)\s+(?P<target>.+)", "complete", ""),
        (r"(?:start|begin)\s+(?P<target>.+)", "start", "task"),
        (r"pause\s+(?P<target>.+)", "pause", "project"),
        (r"activate\s+(?P<target>.+)", "activate", "project"),
        (r"reopen\s+(?P<target>.+)", "reopen", "task"),
        (r"pin\s+(?P<target>.+)", "pin", ""),
        (r"unpin\s+(?P<target>.+)", "unpin", ""),
    )
    for pattern, action, preferred_type in simple_patterns:
        match = re.fullmatch(pattern, command, re.IGNORECASE)
        if match:
            return _resolution_result(
                user, match.group("target"), action, preferred_type=preferred_type, chat=chat
            )

    inspect = re.fullmatch(
        r"(?:open|show|view|inspect|tell me about|status of|what(?:'s| is) the status of)\s+(?P<target>.+)",
        command,
        re.IGNORECASE,
    )
    if inspect:
        return _resolution_result(user, inspect.group("target"), chat=chat)
    return None
