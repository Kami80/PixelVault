import re
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from workspace.models import Activity, Idea, Project, Task, UserSettings

from ..models import PetConversation
from .objects import serialize_workspace_object


OBJECT_REFERENCE = re.compile(
    r"\[(?:project|idea|task|skill):[A-Za-z0-9_-]{1,128}\]",
    re.IGNORECASE,
)
POLITE_PREFIX = re.compile(
    r"^\s*(?:(?:hey|hi|okay|ok)[,!\s]+)?(?:please\s+)?"
    r"(?:(?:can|could|would|will)\s+you\s+|"
    r"i\s+(?:want|need)\s+(?:you\s+)?to\s+|"
    r"i(?:'d|\s+would)\s+like\s+(?:you\s+)?to\s+)?(?:please\s+)?",
    re.IGNORECASE,
)
KIND_PATTERN = r"(?:ideas?|tasks?|to[ -]?dos?|projects?)"
DIRECT_ACTION = re.compile(
    rf"^(?P<verb>add|create|save|capture|record)\s+"
    rf"(?:(?P<reference>this|that|it)\s+(?:as\s+)?)?"
    rf"(?:(?:an?|the|new)\s+)?(?P<kind>{KIND_PATTERN})\b(?P<payload>.*)$",
    re.IGNORECASE,
)
PAYLOAD_ACTION = re.compile(
    rf"^(?P<verb>add|create|save|capture|record)\s+(?P<payload>.+?)\s+"
    rf"as\s+(?:an?\s+)?(?P<kind>{KIND_PATTERN})\s*[.!?]?$",
    re.IGNORECASE,
)
LIST_ACTION = re.compile(
    rf"^(?P<verb>add|save|put|capture)\s+(?P<payload>.+?)\s+"
    rf"(?:to|in)\s+(?:my\s+|the\s+)?(?P<kind>{KIND_PATTERN})"
    rf"(?:\s+list)?\s*[.!?]?$",
    re.IGNORECASE,
)
TURN_ACTION = re.compile(
    rf"^(?P<verb>turn|make)\s+(?P<payload>.+?)\s+"
    rf"(?:into\s+|as\s+)?(?:an?\s+)?(?P<kind>{KIND_PATTERN})\s*[.!?]?$",
    re.IGNORECASE,
)
REFERENCE_WORDS = {
    "this",
    "that",
    "it",
    "this one",
    "that one",
    "this idea",
    "that idea",
    "this task",
    "that task",
    "the idea",
    "the task",
}
ACKNOWLEDGEMENTS = {
    "yes",
    "yeah",
    "yep",
    "ok",
    "okay",
    "great",
    "nice",
    "perfect",
    "thanks",
    "thank you",
    "sounds good",
    "i like it",
    "do it",
}


def _audit_create(user, object_type, item, label):
    Activity.objects.create(
        owner=user,
        verb="created",
        entity_type=object_type,
        entity_id=str(item.pk)[:64],
        label=str(label)[:250],
        metadata={"source": "pet_agent"},
    )


def _plain_text(value):
    text = OBJECT_REFERENCE.sub("", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _normalize_kind(value):
    normalized = re.sub(r"[ -]", "", str(value or "").lower())
    if normalized.startswith("idea"):
        return "idea"
    if normalized.startswith("project"):
        return "project"
    return "task"


def _match_action(message):
    command = POLITE_PREFIX.sub("", _plain_text(message), count=1).strip()
    for pattern in (DIRECT_ACTION, PAYLOAD_ACTION, LIST_ACTION, TURN_ACTION):
        match = pattern.fullmatch(command)
        if match:
            data = match.groupdict()
            return {
                "kind": _normalize_kind(data.get("kind")),
                "payload": str(data.get("payload") or ""),
                "reference": bool(data.get("reference")),
            }
    return None


def _is_reference(value):
    normalized = re.sub(r"[^a-z ]", "", str(value or "").lower()).strip()
    return normalized in REFERENCE_WORDS or normalized in {"based on this", "based on that"}


def _reply_has_useful_context(reply):
    lowered = reply.lower()
    fallback_fragments = (
        "i’m ready",
        "i'm ready",
        "ask me about a project",
        "what should we tackle first",
        "temporary problem",
    )
    return len(reply) >= 20 and not any(fragment in lowered for fragment in fallback_fragments)


def _looks_like_generation_request(message):
    return bool(
        re.search(
            r"\b(suggest|brainstorm|recommend|propose|come up with|give me|what should|any ideas?)\b",
            message,
            re.IGNORECASE,
        )
    )


def _recent_reference(user, chat=None):
    conversations = PetConversation.objects.filter(pet__owner=user)
    if chat is not None:
        conversations = conversations.filter(chat=chat)
    conversations = conversations.only("user_message", "pet_response")[:8]
    for conversation in conversations:
        user_message = _plain_text(conversation.user_message)
        reply = _plain_text(conversation.pet_response)
        if _match_action(user_message):
            continue
        if user_message.lower().rstrip(".!?") in ACKNOWLEDGEMENTS:
            continue
        if _looks_like_generation_request(user_message) and _reply_has_useful_context(reply):
            return reply
        if user_message:
            return user_message
    return ""


def _clean_payload(value, kind):
    text = _plain_text(value).strip(" \t\r\n:;,.!?-–—'\"`")
    text = re.sub(r"\s+please[.!?]*$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^(?:called|named|titled)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:to|about)\s+", "", text, flags=re.IGNORECASE)
    if kind == "idea":
        prefixes = (
            r"^(?:i\s+(?:have|had|got)\s+)?(?:an?\s+)?idea\s*(?:is|would be|to|for|about|:|-)?\s*",
            r"^(?:a\s+(?:strong|good|useful|simple)\s+)?idea\s+(?:is|would be)\s+",
            r"^(?:what if|how about)\s+(?:we|i|you)?\s*",
            r"^(?:i\s+think\s+)?(?:we|i)\s+(?:could|should|can)\s+",
        )
    elif kind == "task":
        prefixes = (
            r"^(?:my|the|your)\s+(?:next\s+)?task\s+(?:is|should be)\s+(?:to\s+)?",
            r"^(?:i|we)\s+(?:need|want|have)\s+to\s+",
            r"^remember\s+to\s+",
            r"^please\s+",
        )
    else:
        prefixes = (
            r"^(?:i|we)\s+(?:want|need)\s+to\s+(?:build|create)\s+",
            r"^(?:a\s+)?project\s+(?:for|to|about|called|named)?\s*",
        )
    for prefix in prefixes:
        updated = re.sub(prefix, "", text, count=1, flags=re.IGNORECASE).strip()
        if updated != text:
            text = updated
            break
    return text.strip(" \t\r\n:;,.!?-–—'\"`")


def _short_title(value, limit):
    first_line = str(value or "").splitlines()[0].strip()
    first_sentence = re.split(r"(?<=[.!?])\s+", first_line, maxsplit=1)[0].rstrip(".!?")
    title = first_sentence or first_line
    if len(title) > limit:
        shortened = title[: limit + 1].rsplit(" ", 1)[0].rstrip(" ,:;.-")
        title = shortened or title[:limit]
    if title and title[0].islower():
        title = title[0].upper() + title[1:]
    return title


def _title_payload(value):
    text = re.sub(
        r"\s*[,;(-]?\s*(?:due|by)\s+(?:today|tomorrow|\d{4}-\d{2}-\d{2})\s*\)?",
        "",
        value,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\s*[,;(-]?\s*(?:(?:with\s+)?(?:high|medium|low)[ -]priority|"
        r"priority\s*[:=-]?\s*(?:high|medium|low))\s*\)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", text).strip(" ,;:-–—") or value


def _priority_from(text):
    match = re.search(r"\b(high|medium|low)[ -]priority\b", text, re.IGNORECASE)
    if not match:
        match = re.search(r"\bpriority\s*[:=-]?\s*(high|medium|low)\b", text, re.IGNORECASE)
    return match.group(1).lower() if match else "medium"


def _due_date_from(text):
    if re.search(r"\b(?:due|by)\s+today\b", text, re.IGNORECASE):
        return timezone.localdate()
    if re.search(r"\b(?:due|by)\s+tomorrow\b", text, re.IGNORECASE):
        return timezone.localdate() + timedelta(days=1)
    match = re.search(r"\b(?:due|by)\s+(\d{4}-\d{2}-\d{2})\b", text, re.IGNORECASE)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


def _mentioned_project(user, text):
    normalized = text.casefold()
    projects = Project.objects.filter(owner=user).only("id", "title").order_by("-updated_on")
    matches = []
    for project in projects:
        title = project.title.strip()
        if len(title) < 3:
            continue
        pattern = rf"(?<!\w){re.escape(title.casefold())}(?!\w)"
        if re.search(pattern, normalized):
            matches.append(project)
    return max(matches, key=lambda project: len(project.title), default=None)


def _missing_content_result(kind):
    noun = kind
    examples = {
        "idea": "add an idea: build a weekly review dashboard",
        "task": "add a task: draft the launch checklist",
        "project": "create a project: launch the new portfolio",
    }
    example = examples[kind]
    return {
        "message": f"Tell me the {noun} first, then say “add this {noun}” — or write “{example}.”",
        "emotion": "focused",
        "objects": [],
        "action": {"status": "needs_input", "objectType": kind},
    }


@transaction.atomic
def handle_workspace_action(user, message, chat=None):
    """Create an idea, task, or project only after an explicit save command."""
    action = _match_action(message)
    if not action:
        return None

    kind = action["kind"]
    raw_payload = action["payload"]
    if action["reference"] or _is_reference(raw_payload) or not raw_payload.strip(" :;,.!?-–—"):
        raw_payload = _recent_reference(user, chat)
    payload = _clean_payload(raw_payload, kind)
    if not payload:
        return _missing_content_result(kind)

    project = _mentioned_project(user, payload)
    if kind == "idea":
        title = _short_title(_title_payload(payload), Idea._meta.get_field("title").max_length)
        if not title:
            return _missing_content_result(kind)
        idea = Idea.objects.create(
            owner=user,
            title=title,
            description=payload if payload.casefold() != title.casefold() else "",
            content_type="note",
            status="inbox",
            priority=_priority_from(payload),
            project=project,
        )
        _audit_create(user, "idea", idea, idea.title)
        workspace_object = serialize_workspace_object("idea", idea)
        project_note = f" under {project.title}" if project else ""
        return {
            "message": f"Added “{idea.title}” to your idea inbox{project_note}. [idea:{idea.pk}]",
            "emotion": "happy",
            "objects": [workspace_object],
            "action": {"status": "created", "objectType": "idea", "objectId": str(idea.pk)},
        }

    if kind == "project":
        title = _short_title(_title_payload(payload), Project._meta.get_field("title").max_length)
        if not title:
            return _missing_content_result(kind)
        project = Project.objects.create(
            owner=user,
            title=title,
            description=payload if payload.casefold() != title.casefold() else "",
            status="active",
        )
        _audit_create(user, "project", project, project.title)
        return {
            "message": f"Created the active project “{project.title}.” [project:{project.pk}]",
            "emotion": "happy",
            "objects": [serialize_workspace_object("project", project)],
            "action": {"status": "created", "objectType": "project", "objectId": str(project.pk)},
        }

    title = _short_title(_title_payload(payload), Task._meta.get_field("title").max_length)
    if not title:
        return _missing_content_result(kind)
    settings_obj = UserSettings.objects.filter(user=user).only("default_task_duration").first()
    due_date = _due_date_from(payload)
    task = Task.objects.create(
        owner=user,
        title=title,
        description=payload if payload.casefold() != title.casefold() else "",
        project=project,
        status="todo",
        priority=_priority_from(payload),
        duration_minutes=settings_obj.default_task_duration if settings_obj else 45,
        due_date=due_date,
    )
    _audit_create(user, "task", task, task.title)
    workspace_object = serialize_workspace_object("task", task)
    details = []
    if project:
        details.append(f"in {project.title}")
    if due_date:
        details.append(f"due {due_date.isoformat()}")
    detail_text = f" ({', '.join(details)})" if details else ""
    return {
        "message": f"Added “{task.title}” to your tasks{detail_text}. [task:{task.pk}]",
        "emotion": "happy",
        "objects": [workspace_object],
        "action": {"status": "created", "objectType": "task", "objectId": str(task.pk)},
    }
