import json
import re
from datetime import date, datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time

from pet.models import PetChatSession, PetConversation, PetMemory, PetProfile
from workspace.models import Activity, Annotation, Idea, Project, Skill, Task, UserSettings

from .objects import serialize_workspace_object


READABLE_TYPES = (
    "project",
    "idea",
    "task",
    "skill",
    "annotation",
    "memory",
    "chat",
    "message",
    "pet",
    "activity",
    "settings",
)
CREATABLE_TYPES = ("project", "idea", "task", "skill", "annotation", "memory")
UPDATABLE_TYPES = (*CREATABLE_TYPES, "chat", "pet", "settings")
DELETABLE_TYPES = (*CREATABLE_TYPES, "chat")
CARD_TYPES = {"project", "idea", "task", "skill"}
MAX_QUERY_LIMIT = 25
MAX_TOOL_TEXT = 60_000
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:password|secret|token|api[_-]?key|workspace[_-]?root|local[_-]?path)",
    re.IGNORECASE,
)


FIELD_ALIASES = {
    "projectId": "project_id",
    "dependsOn": "depends_on_id",
    "contentType": "content_type",
    "sourceUrl": "source_url",
    "liveSiteUrl": "live_site_url",
    "launchUrl": "launch_url",
    "repositoryUrl": "repository_url",
    "githubPagesUrl": "github_pages_url",
    "techStack": "tech_stack",
    "isWeb": "is_web",
    "targetDate": "target_date",
    "nextMilestone": "next_milestone",
    "nextAction": "next_action",
    "taskType": "task_type",
    "scheduledDate": "scheduled_date",
    "dueDate": "due_date",
    "startTime": "start_time",
    "durationMinutes": "duration_minutes",
    "memoryType": "memory_type",
    "relatedType": "related_type",
    "relatedId": "related_id",
    "pageKey": "page_key",
    "selectedText": "selected_text",
    "displayName": "display_name",
    "workspaceName": "workspace_name",
    "socialHandle": "social_handle",
    "reduceMotion": "reduce_motion",
    "showGrid": "show_grid",
    "showMascots": "show_mascots",
    "confirmDeletes": "confirm_deletes",
    "highContrast": "high_contrast",
    "largeTargets": "large_targets",
    "landingPage": "landing_page",
    "plannerDefaultView": "planner_default_view",
    "plannerView": "planner_view",
    "plannerAnchor": "planner_anchor",
    "weekStart": "week_start",
    "workdayStart": "workday_start",
    "workdayEnd": "workday_end",
    "defaultTaskDuration": "default_task_duration",
    "plannerSnapMinutes": "planner_snap_minutes",
    "plannerHourPx": "planner_hour_px",
    "defaultHighlight": "default_highlight",
    "showHighlights": "show_highlights",
    "skillSelected": "skill_selected",
}


FIELD_RULES = {
    "project": {
        "title": ("string", 180),
        "description": ("text", 20_000),
        "tags": ("list",),
        "status": ("choice",),
        "progress": ("integer", 0, 100),
        "launch_url": ("string", 1_000),
        "repository_url": ("string", 1_000),
        "github_pages_url": ("string", 1_000),
        "tech_stack": ("list",),
        "is_web": ("boolean",),
        "target_date": ("date", True),
        "goal": ("text", 20_000),
        "next_milestone": ("string", 500),
        "notes": ("text", 30_000),
        "pinned": ("boolean",),
    },
    "idea": {
        "title": ("string", 180),
        "description": ("text", 20_000),
        "content_type": ("choice",),
        "content": ("text", 30_000),
        "status": ("choice",),
        "priority": ("choice",),
        "goal": ("text", 20_000),
        "audience": ("string", 180),
        "source_url": ("string", 1_000),
        "live_site_url": ("string", 1_000),
        "tags": ("list",),
        "project_id": ("project", True),
        "next_action": ("string", 500),
        "pinned": ("boolean",),
    },
    "task": {
        "title": ("string", 220),
        "description": ("text", 20_000),
        "project_id": ("project", True),
        "status": ("choice",),
        "priority": ("choice",),
        "task_type": ("string", 40),
        "energy": ("choice",),
        "scheduled_date": ("date", True),
        "due_date": ("date", True),
        "start_time": ("time", True),
        "duration_minutes": ("integer", 1, 1_440),
        "recurrence": ("choice",),
        "depends_on_id": ("task", True),
        "subtasks": ("list",),
        "tags": ("list",),
        "notes": ("text", 30_000),
        "pinned": ("boolean",),
    },
    "skill": {
        "name": ("string", 180),
        "description": ("text", 20_000),
        "category": ("string", 100),
        "version": ("string", 40),
        "source_url": ("string", 1_000),
        "tags": ("list",),
        "agents": ("list",),
        "use_cases": ("list",),
        "filename": ("string", 255),
        "content": ("text", MAX_TOOL_TEXT),
        "pinned": ("boolean",),
    },
    "annotation": {
        "page_key": ("string", 40),
        "selected_text": ("text", 30_000),
        "prefix": ("text", 10_000),
        "suffix": ("text", 10_000),
        "color": ("choice",),
        "comment": ("text", 20_000),
    },
    "memory": {
        "memory_type": ("choice",),
        "content": ("text", 30_000),
        "importance": ("integer", 0, 100),
        "confidence": ("float", 0.0, 1.0),
        "related_type": ("string", 40),
        "related_id": ("string", 120),
    },
    "chat": {"title": ("string", 120)},
    "pet": {"name": ("string", 50)},
    "settings": {
        "display_name": ("string", 60),
        "role": ("string", 80),
        "workspace_name": ("string", 60),
        "social_handle": ("string", 60),
        "bio": ("string", 280),
        "avatar": ("string", 64),
        "theme": ("choice",),
        "accent": ("choice",),
        "density": ("choice",),
        "text_size": ("choice",),
        "reduce_motion": ("boolean",),
        "show_grid": ("boolean",),
        "show_mascots": ("boolean",),
        "confirm_deletes": ("boolean",),
        "high_contrast": ("boolean",),
        "large_targets": ("boolean",),
        "landing_page": ("choice",),
        "planner_default_view": ("choice",),
        "planner_view": ("choice",),
        "planner_anchor": ("date", False),
        "week_start": ("choice",),
        "workday_start": ("integer", 0, 23),
        "workday_end": ("integer", 1, 24),
        "default_task_duration": ("integer", 5, 1_440),
        "planner_snap_minutes": ("integer", 15, 60),
        "planner_hour_px": ("integer", 64, 144),
        "default_highlight": ("choice",),
        "show_highlights": ("boolean",),
        "signature": ("string", 80),
        "skill_selected": ("string", 64),
    },
}


FIELD_GUIDE = {
    object_type: ", ".join(rules)
    for object_type, rules in FIELD_RULES.items()
}


DATABASE_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "workspace_overview",
            "description": (
                "Get authoritative counts and current workload summaries for the signed-in user's "
                "PixelVault workspace. Use this before broad planning or status questions."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_records",
            "description": (
                "Search and filter the signed-in user's records. This is the only database scope you "
                "can access. Search text is matched against useful fields, not just titles."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "object_type": {"type": "string", "enum": list(READABLE_TYPES)},
                    "query": {"type": "string", "description": "Optional words to search for."},
                    "status": {"type": "string", "description": "Optional exact status."},
                    "priority": {"type": "string", "description": "Optional exact priority."},
                    "project_id": {"type": "string", "description": "Optional owning project ID."},
                    "chat_id": {"type": "string", "description": "Optional chat ID for message records."},
                    "due": {
                        "type": "string",
                        "description": "Optional: overdue, today, upcoming, unscheduled, or YYYY-MM-DD.",
                    },
                    "limit": {"type": "integer", "minimum": 1, "maximum": MAX_QUERY_LIMIT},
                },
                "required": ["object_type"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_record",
            "description": (
                "Read one complete owned record, including its useful relationships and long-form "
                "content. Never guess an ID; query first when needed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "object_type": {"type": "string", "enum": list(READABLE_TYPES)},
                    "object_id": {"type": "string"},
                },
                "required": ["object_type", "object_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_record",
            "description": (
                "Create a record only when the user's latest message explicitly asks to create, add, "
                "save, or remember it. Allowed fields by type: "
                + "; ".join(f"{kind}: {FIELD_GUIDE[kind]}" for kind in CREATABLE_TYPES)
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "object_type": {"type": "string", "enum": list(CREATABLE_TYPES)},
                    "fields": {"type": "object"},
                },
                "required": ["object_type", "fields"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_record",
            "description": (
                "Update an owned record only when the user's latest message explicitly asks for the "
                "change. Use project_id or depends_on_id to relate records. Allowed fields by type: "
                + "; ".join(f"{kind}: {FIELD_GUIDE[kind]}" for kind in UPDATABLE_TYPES)
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "object_type": {"type": "string", "enum": list(UPDATABLE_TYPES)},
                    "object_id": {"type": "string"},
                    "fields": {"type": "object"},
                },
                "required": ["object_type", "object_id", "fields"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_record",
            "description": (
                "Delete one owned record. Call only after the user explicitly confirms this exact "
                "deletion in their latest message. Never treat a general cleanup request as confirmation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "object_type": {"type": "string", "enum": list(DELETABLE_TYPES)},
                    "object_id": {"type": "string"},
                    "confirmed": {
                        "type": "boolean",
                        "description": "True only when the latest user message explicitly confirms deletion.",
                    },
                },
                "required": ["object_type", "object_id", "confirmed"],
                "additionalProperties": False,
            },
        },
    },
]


class DatabaseToolError(Exception):
    def __init__(self, message, *, code="invalid_request"):
        super().__init__(message)
        self.code = code


def _iso(value):
    return value.isoformat() if value else None


def _limited_text(value, limit):
    text = str(value or "")
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n… [truncated; {len(text) - limit} more characters]"


def _safe_json(value, depth=0):
    if depth > 5:
        return "[nested data omitted]"
    if isinstance(value, dict):
        return {
            str(key): _safe_json(item, depth + 1)
            for key, item in value.items()
            if not SENSITIVE_KEY_PATTERN.search(str(key))
        }
    if isinstance(value, (list, tuple)):
        return [_safe_json(item, depth + 1) for item in value[:100]]
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _limited_text(value, 4_000)


def _settings_record(item):
    return {
        "type": "settings",
        "id": "settings",
        "display_name": item.display_name,
        "role": item.role,
        "workspace_name": item.workspace_name,
        "social_handle": item.social_handle,
        "bio": item.bio,
        "avatar": item.avatar,
        "theme": item.theme,
        "accent": item.accent,
        "density": item.density,
        "text_size": item.text_size,
        "reduce_motion": item.reduce_motion,
        "show_grid": item.show_grid,
        "show_mascots": item.show_mascots,
        "confirm_deletes": item.confirm_deletes,
        "high_contrast": item.high_contrast,
        "large_targets": item.large_targets,
        "landing_page": item.landing_page,
        "planner_default_view": item.planner_default_view,
        "planner_view": item.planner_view,
        "planner_anchor": _iso(item.planner_anchor),
        "week_start": item.week_start,
        "workday_start": item.workday_start,
        "workday_end": item.workday_end,
        "default_task_duration": item.default_task_duration,
        "planner_snap_minutes": item.planner_snap_minutes,
        "planner_hour_px": item.planner_hour_px,
        "default_highlight": item.default_highlight,
        "show_highlights": item.show_highlights,
        "signature": item.signature,
        "skill_selected": item.skill_selected,
        "local_workspace_boundary_configured": bool(item.workspace_root),
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }


def serialize_database_record(object_type, item, *, detail=True):
    text_limit = 12_000 if detail else 2_000
    if object_type == "project":
        owned_tasks = item.tasks.filter(owner=item.owner)
        owned_ideas = item.ideas.filter(owner=item.owner)
        return {
            "type": object_type,
            "id": str(item.pk),
            "title": item.title,
            "description": _limited_text(item.description, text_limit),
            "tags": item.tags or [],
            "status": item.status,
            "progress": item.progress,
            "launch_url": item.launch_url,
            "repository_url": item.repository_url,
            "github_pages_url": item.github_pages_url,
            "tech_stack": item.tech_stack or [],
            "is_web": item.is_web,
            "target_date": _iso(item.target_date),
            "goal": _limited_text(item.goal, text_limit),
            "next_milestone": item.next_milestone,
            "notes": _limited_text(item.notes, text_limit),
            "pinned": item.pinned,
            "local_path_configured": bool(item.local_path),
            "task_ids": list(owned_tasks.values_list("id", flat=True)[:100]),
            "idea_ids": list(owned_ideas.values_list("id", flat=True)[:100]),
            "open_task_count": owned_tasks.exclude(status="done").count(),
            "created_on": _iso(item.created_on),
            "updated_on": _iso(item.updated_on),
        }
    if object_type == "idea":
        owned_project = item.project if item.project_id and item.project.owner_id == item.owner_id else None
        return {
            "type": object_type,
            "id": str(item.pk),
            "title": item.title,
            "description": _limited_text(item.description, text_limit),
            "content_type": item.content_type,
            "content": _limited_text(item.content, text_limit),
            "status": item.status,
            "priority": item.priority,
            "goal": _limited_text(item.goal, text_limit),
            "audience": item.audience,
            "source_url": item.source_url,
            "live_site_url": item.live_site_url,
            "tags": item.tags or [],
            "project_id": owned_project.pk if owned_project else None,
            "project_title": owned_project.title if owned_project else None,
            "next_action": item.next_action,
            "pinned": item.pinned,
            "created_on": _iso(item.created_on),
            "updated_on": _iso(item.updated_on),
        }
    if object_type == "task":
        owned_project = item.project if item.project_id and item.project.owner_id == item.owner_id else None
        owned_dependency = (
            item.depends_on
            if item.depends_on_id and item.depends_on.owner_id == item.owner_id
            else None
        )
        return {
            "type": object_type,
            "id": str(item.pk),
            "title": item.title,
            "description": _limited_text(item.description, text_limit),
            "project_id": owned_project.pk if owned_project else None,
            "project_title": owned_project.title if owned_project else None,
            "status": item.status,
            "priority": item.priority,
            "task_type": item.task_type,
            "energy": item.energy,
            "scheduled_date": _iso(item.scheduled_date),
            "due_date": _iso(item.due_date),
            "start_time": _iso(item.start_time),
            "duration_minutes": item.duration_minutes,
            "recurrence": item.recurrence,
            "depends_on_id": owned_dependency.pk if owned_dependency else None,
            "dependent_task_ids": list(
                item.dependent_tasks.filter(owner=item.owner).values_list("id", flat=True)[:100]
            ),
            "subtasks": item.subtasks or [],
            "tags": item.tags or [],
            "notes": _limited_text(item.notes, text_limit),
            "pinned": item.pinned,
            "completed_on": _iso(item.completed_on),
            "created_on": _iso(item.created_on),
            "updated_on": _iso(item.updated_on),
        }
    if object_type == "skill":
        return {
            "type": object_type,
            "id": str(item.pk),
            "name": item.name,
            "description": _limited_text(item.description, text_limit),
            "category": item.category,
            "version": item.version,
            "source_url": item.source_url,
            "tags": item.tags or [],
            "agents": item.agents or [],
            "use_cases": item.use_cases or [],
            "filename": item.filename,
            "content": _limited_text(item.content, text_limit),
            "attachment_configured": bool(item.attached_file),
            "pinned": item.pinned,
            "created_on": _iso(item.created_on),
            "updated_on": _iso(item.updated_on),
        }
    if object_type == "annotation":
        return {
            "type": object_type,
            "id": str(item.pk),
            "page_key": item.page_key,
            "selected_text": _limited_text(item.selected_text, text_limit),
            "prefix": _limited_text(item.prefix, text_limit),
            "suffix": _limited_text(item.suffix, text_limit),
            "color": item.color,
            "comment": _limited_text(item.comment, text_limit),
            "created_at": _iso(item.created_at),
        }
    if object_type == "memory":
        return {
            "type": object_type,
            "id": str(item.pk),
            "memory_type": item.memory_type,
            "content": _limited_text(item.content, text_limit),
            "importance": item.importance,
            "confidence": item.confidence,
            "related_type": item.related_type,
            "related_id": item.related_id,
            "created_at": _iso(item.created_at),
        }
    if object_type == "chat":
        record = {
            "type": object_type,
            "id": str(item.pk),
            "title": item.title,
            "message_count": item.conversations.count(),
            "created_at": _iso(item.created_at),
            "updated_at": _iso(item.updated_at),
        }
        if detail:
            conversations = list(item.conversations.filter(pet__owner=item.pet.owner)[:30])
            record["recent_messages"] = [
                {
                    "user": _limited_text(conversation.user_message, 3_000),
                    "assistant": _limited_text(conversation.pet_response, 3_000),
                    "emotion": conversation.emotion,
                    "created_at": _iso(conversation.created_at),
                }
                for conversation in reversed(conversations)
            ]
        return record
    if object_type == "message":
        owned_chat = (
            item.chat
            if item.chat_id and item.chat.pet.owner_id == item.pet.owner_id
            else None
        )
        return {
            "type": object_type,
            "id": str(item.pk),
            "chat_id": str(owned_chat.pk) if owned_chat else None,
            "chat_title": owned_chat.title if owned_chat else None,
            "user_message": _limited_text(item.user_message, text_limit),
            "assistant_message": _limited_text(item.pet_response, text_limit),
            "emotion": item.emotion,
            "created_at": _iso(item.created_at),
        }
    if object_type == "pet":
        return {
            "type": object_type,
            "id": "pet",
            "name": item.name,
            "level": item.level,
            "xp": item.xp,
            "happiness": item.happiness,
            "energy": item.energy,
            "curiosity": item.curiosity,
            "focus": item.focus,
            "current_state": item.current_state,
            "created_at": _iso(item.created_at),
        }
    if object_type == "activity":
        return {
            "type": object_type,
            "id": str(item.pk),
            "verb": item.verb,
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
            "label": item.label,
            "metadata": _safe_json(item.metadata),
            "created_at": _iso(item.created_at),
        }
    if object_type == "settings":
        return _settings_record(item)
    raise DatabaseToolError("That record type is not available.", code="unsupported_type")


def _owned_queryset(user, object_type):
    if object_type == "project":
        return Project.objects.filter(owner=user)
    if object_type == "idea":
        return Idea.objects.filter(owner=user).select_related("project")
    if object_type == "task":
        return Task.objects.filter(owner=user).select_related("project", "depends_on")
    if object_type == "skill":
        return Skill.objects.filter(owner=user)
    if object_type == "annotation":
        return Annotation.objects.filter(owner=user)
    if object_type == "memory":
        return PetMemory.objects.filter(owner=user)
    if object_type == "chat":
        return PetChatSession.objects.filter(pet__owner=user)
    if object_type == "message":
        return PetConversation.objects.filter(pet__owner=user).select_related("chat")
    if object_type == "pet":
        return PetProfile.objects.filter(owner=user)
    if object_type == "activity":
        return Activity.objects.filter(owner=user)
    if object_type == "settings":
        return UserSettings.objects.filter(user=user)
    raise DatabaseToolError("That record type is not available.", code="unsupported_type")


def _get_owned_record(user, object_type, object_id):
    if object_type not in READABLE_TYPES:
        raise DatabaseToolError("That record type is not available.", code="unsupported_type")
    if object_type in {"settings", "pet"}:
        special_id = object_type
        if str(object_id or special_id) not in {"", special_id}:
            raise DatabaseToolError(f"{object_type.title()} uses the ID '{special_id}'.", code="not_found")
        if object_type == "settings":
            item, _ = UserSettings.objects.get_or_create(user=user)
        else:
            item, _ = PetProfile.objects.get_or_create(owner=user)
        return item
    identifier = str(object_id or "").strip()
    if not ID_PATTERN.fullmatch(identifier):
        raise DatabaseToolError("That record does not exist in your workspace.", code="not_found")
    queryset = _owned_queryset(user, object_type)
    try:
        return queryset.get(pk=identifier)
    except (ValueError, TypeError, queryset.model.DoesNotExist) as exc:
        raise DatabaseToolError(
            "That record does not exist in your workspace.", code="not_found"
        ) from exc


def workspace_overview(user):
    today = timezone.localdate()
    projects = Project.objects.filter(owner=user)
    ideas = Idea.objects.filter(owner=user)
    tasks = Task.objects.filter(owner=user)
    return {
        "current_date": today.isoformat(),
        "projects": {
            "total": projects.count(),
            "active": projects.filter(status="active").count(),
            "paused": projects.filter(status="paused").count(),
            "done": projects.filter(status="done").count(),
        },
        "ideas": {
            "total": ideas.count(),
            "inbox": ideas.filter(status="inbox").count(),
            "exploring": ideas.filter(status="exploring").count(),
            "ready": ideas.filter(status="ready").count(),
            "building": ideas.filter(status="building").count(),
        },
        "tasks": {
            "total": tasks.count(),
            "todo": tasks.filter(status="todo").count(),
            "doing": tasks.filter(status="doing").count(),
            "done": tasks.filter(status="done").count(),
            "overdue": tasks.exclude(status="done").filter(due_date__lt=today).count(),
            "due_today": tasks.exclude(status="done").filter(due_date=today).count(),
        },
        "skills": Skill.objects.filter(owner=user).count(),
        "annotations": Annotation.objects.filter(owner=user).count(),
        "memories": PetMemory.objects.filter(owner=user).count(),
        "chats": PetChatSession.objects.filter(pet__owner=user).count(),
        "chat_messages": PetConversation.objects.filter(pet__owner=user).count(),
        "activity_entries": Activity.objects.filter(owner=user).count(),
    }


SEARCH_FIELDS = {
    "project": ("title", "description", "goal", "next_milestone", "notes"),
    "idea": ("title", "description", "content", "goal", "audience", "next_action"),
    "task": ("title", "description", "notes", "task_type"),
    "skill": ("name", "description", "category", "content", "filename"),
    "annotation": ("page_key", "selected_text", "comment", "prefix", "suffix"),
    "memory": ("memory_type", "content", "related_type", "related_id"),
    "activity": ("verb", "entity_type", "entity_id", "label"),
    "message": ("user_message", "pet_response", "emotion"),
    "pet": ("name", "current_state"),
    "settings": ("display_name", "role", "workspace_name", "social_handle", "bio"),
}


def _query_records(user, arguments):
    object_type = str(arguments.get("object_type") or "").strip().lower()
    if object_type not in READABLE_TYPES:
        raise DatabaseToolError("Choose a supported record type.", code="unsupported_type")
    queryset = _owned_queryset(user, object_type)
    query = _limited_text(arguments.get("query"), 500).strip()
    if query:
        terms = re.findall(r"[A-Za-z0-9_-]{2,}", query)[:8] or [query]
        if object_type == "chat":
            lookup = Q()
            for term in terms:
                lookup |= Q(title__icontains=term) | Q(conversations__user_message__icontains=term)
                lookup |= Q(conversations__pet_response__icontains=term)
            queryset = queryset.filter(lookup).distinct()
        else:
            lookup = Q()
            search_fields = SEARCH_FIELDS.get(object_type, ())
            for term in terms:
                for field in search_fields:
                    lookup |= Q(**{f"{field}__icontains": term})
            if search_fields:
                queryset = queryset.filter(lookup)

    status = str(arguments.get("status") or "").strip().lower()
    if status and object_type in {"project", "idea", "task"}:
        queryset = queryset.filter(status=status)
    priority = str(arguments.get("priority") or "").strip().lower()
    if priority and object_type in {"idea", "task"}:
        queryset = queryset.filter(priority=priority)
    project_id = str(arguments.get("project_id") or "").strip()
    if project_id and object_type in {"idea", "task"}:
        project = _get_owned_record(user, "project", project_id)
        queryset = queryset.filter(project=project)
    chat_id = str(arguments.get("chat_id") or "").strip()
    if chat_id and object_type == "message":
        chat = _get_owned_record(user, "chat", chat_id)
        queryset = queryset.filter(chat=chat)

    due = str(arguments.get("due") or "").strip().lower()
    if due and object_type in {"task", "project"}:
        due_field = "due_date" if object_type == "task" else "target_date"
        today = timezone.localdate()
        if due == "overdue":
            queryset = queryset.filter(**{f"{due_field}__lt": today})
            if object_type == "task":
                queryset = queryset.exclude(status="done")
        elif due == "today":
            queryset = queryset.filter(**{due_field: today})
        elif due == "upcoming":
            queryset = queryset.filter(**{f"{due_field}__gte": today})
        elif due == "unscheduled":
            queryset = queryset.filter(**{f"{due_field}__isnull": True})
        else:
            parsed = parse_date(due)
            if parsed is None:
                raise DatabaseToolError(
                    "Due must be overdue, today, upcoming, unscheduled, or YYYY-MM-DD."
                )
            queryset = queryset.filter(**{due_field: parsed})

    try:
        limit = int(arguments.get("limit") or 10)
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(limit, MAX_QUERY_LIMIT))
    items = list(queryset[:limit])
    records = [serialize_database_record(object_type, item, detail=False) for item in items]
    return {
        "ok": True,
        "object_type": object_type,
        "count": len(records),
        "records": records,
        "references": _references(object_type, items[:5]),
    }


def _references(object_type, items):
    if object_type not in CARD_TYPES:
        return []
    return [{"type": object_type, "id": str(item.pk)} for item in items]


def _as_bool(value):
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise DatabaseToolError("Use true or false for boolean fields.")


def _as_list(value):
    if isinstance(value, list):
        return [_limited_text(item, 500).strip() for item in value if str(item).strip()][:100]
    if value in {None, ""}:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()][:100]


def _as_date(value, nullable):
    if value in {None, ""} and nullable:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    normalized = str(value or "").strip().lower()
    if normalized == "today":
        return timezone.localdate()
    if normalized == "tomorrow":
        return timezone.localdate() + timedelta(days=1)
    parsed = parse_date(normalized)
    if parsed is None:
        raise DatabaseToolError("Use a date like 2026-09-15, today, or tomorrow.")
    return parsed


def _as_time(value, nullable):
    if value in {None, ""} and nullable:
        return None
    if isinstance(value, time):
        return value
    parsed = parse_time(str(value or "").strip())
    if parsed is None:
        raise DatabaseToolError("Use a time like 09:30.")
    return parsed


def _coerce_fields(user, object_type, raw_fields, instance=None):
    if not isinstance(raw_fields, dict) or not raw_fields:
        raise DatabaseToolError("Provide at least one field to save.")
    rules = FIELD_RULES.get(object_type, {})
    fields = {FIELD_ALIASES.get(str(key), str(key)): value for key, value in raw_fields.items()}
    unknown = sorted(set(fields) - set(rules))
    if unknown:
        raise DatabaseToolError(
            f"Unsupported {object_type} field{'s' if len(unknown) != 1 else ''}: {', '.join(unknown)}."
        )

    cleaned = {}
    for field_name, value in fields.items():
        rule = rules[field_name]
        kind = rule[0]
        if kind in {"string", "text"}:
            cleaned[field_name] = _limited_text(value, rule[1]).strip() if kind == "string" else _limited_text(value, rule[1])
            if object_type == "skill" and field_name == "filename":
                cleaned[field_name] = cleaned[field_name].replace("\\", "/").rsplit("/", 1)[-1]
        elif kind == "list":
            cleaned[field_name] = _as_list(value)
        elif kind == "boolean":
            cleaned[field_name] = _as_bool(value)
        elif kind == "integer":
            try:
                number = int(value)
            except (TypeError, ValueError) as exc:
                raise DatabaseToolError(f"{field_name} must be a whole number.") from exc
            if not rule[1] <= number <= rule[2]:
                raise DatabaseToolError(f"{field_name} must be from {rule[1]} to {rule[2]}.")
            cleaned[field_name] = number
        elif kind == "float":
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise DatabaseToolError(f"{field_name} must be a number.") from exc
            if not rule[1] <= number <= rule[2]:
                raise DatabaseToolError(f"{field_name} must be from {rule[1]} to {rule[2]}.")
            cleaned[field_name] = number
        elif kind == "date":
            cleaned[field_name] = _as_date(value, rule[1])
        elif kind == "time":
            cleaned[field_name] = _as_time(value, rule[1])
        elif kind == "choice":
            model_field = instance._meta.get_field(field_name) if instance is not None else None
            if model_field is None:
                model = {
                    "project": Project,
                    "idea": Idea,
                    "task": Task,
                    "annotation": Annotation,
                    "memory": PetMemory,
                    "settings": UserSettings,
                }.get(object_type)
                model_field = model._meta.get_field(field_name)
            allowed = {choice for choice, _label in model_field.choices}
            normalized = str(value or "").strip().lower()
            if normalized not in allowed:
                raise DatabaseToolError(
                    f"{field_name} must be one of: {', '.join(sorted(allowed))}."
                )
            cleaned[field_name] = normalized
        elif kind == "project":
            if value in {None, ""} and rule[1]:
                cleaned["project"] = None
            else:
                cleaned["project"] = _get_owned_record(user, "project", value)
        elif kind == "task":
            if value in {None, ""} and rule[1]:
                cleaned["depends_on"] = None
            else:
                dependency = _get_owned_record(user, "task", value)
                if instance is not None and dependency.pk == instance.pk:
                    raise DatabaseToolError("A task cannot depend on itself.")
                cleaned["depends_on"] = dependency
    return cleaned


def _required_field(object_type):
    return {
        "project": "title",
        "idea": "title",
        "task": "title",
        "skill": "name",
        "annotation": "selected_text",
        "memory": "content",
    }[object_type]


def _record_label(object_type, item):
    if object_type in {"project", "idea", "task"}:
        return item.title
    if object_type == "skill":
        return item.name
    if object_type == "annotation":
        return item.selected_text[:120]
    if object_type == "memory":
        return item.content[:120]
    if object_type == "chat":
        return item.title
    if object_type == "pet":
        return item.name
    return object_type.title()


def _log_write(user, verb, object_type, item_id, label, changed_fields=None):
    metadata = {"source": "pet_agent"}
    if changed_fields:
        metadata["changed_fields"] = sorted(changed_fields)
    Activity.objects.create(
        owner=user,
        verb=verb,
        entity_type=object_type,
        entity_id=str(item_id)[:64],
        label=str(label)[:250],
        metadata=metadata,
    )


def _validate_and_save(item):
    try:
        item.full_clean()
    except ValidationError as exc:
        messages = []
        if hasattr(exc, "message_dict"):
            for field, errors in exc.message_dict.items():
                messages.append(f"{field}: {'; '.join(errors)}")
        else:
            messages.extend(exc.messages)
        raise DatabaseToolError(" ".join(messages)[:800] or "The record is not valid.") from exc
    item.save()


def _validate_task_dependency(item):
    current = item.depends_on
    seen = set()
    while current is not None:
        if current.pk == item.pk:
            raise DatabaseToolError("That dependency would create a task cycle.")
        if current.pk in seen:
            raise DatabaseToolError("The selected dependency already contains a task cycle.")
        seen.add(current.pk)
        current = current.depends_on


def _validate_settings_consistency(item):
    if item.workday_end <= item.workday_start:
        raise DatabaseToolError("workday_end must be later than workday_start.")
    if item.planner_snap_minutes not in {15, 30, 60}:
        raise DatabaseToolError("planner_snap_minutes must be 15, 30, or 60.")


@transaction.atomic
def _create_record(user, object_type, fields):
    if object_type not in CREATABLE_TYPES:
        raise DatabaseToolError("That record type cannot be created by the pet.", code="read_only")
    model = {
        "project": Project,
        "idea": Idea,
        "task": Task,
        "skill": Skill,
        "annotation": Annotation,
        "memory": PetMemory,
    }[object_type]
    item = model(owner=user)
    cleaned = _coerce_fields(user, object_type, fields, instance=item)
    required = _required_field(object_type)
    if not str(cleaned.get(required) or "").strip():
        raise DatabaseToolError(f"{required} is required.")
    for field_name, value in cleaned.items():
        setattr(item, field_name, value)
    if object_type == "annotation" and not item.page_key:
        item.page_key = "pet"
    if object_type == "task" and item.status == "done":
        item.completed_on = timezone.localdate()
    if object_type == "task":
        _validate_task_dependency(item)
    if object_type == "project":
        if item.status == "done" or item.progress == 100:
            item.status = "done"
            item.progress = 100
    _validate_and_save(item)
    label = _record_label(object_type, item)
    _log_write(user, "created", object_type, item.pk, label, cleaned)
    return {
        "ok": True,
        "operation": "created",
        "object_type": object_type,
        "record": serialize_database_record(object_type, item),
        "references": _references(object_type, [item]),
    }


@transaction.atomic
def _update_record(user, object_type, object_id, fields):
    if object_type not in UPDATABLE_TYPES:
        raise DatabaseToolError("That record type is read-only.", code="read_only")
    item = _get_owned_record(user, object_type, object_id)
    cleaned = _coerce_fields(user, object_type, fields, instance=item)
    for field_name, value in cleaned.items():
        setattr(item, field_name, value)
    if hasattr(item, "updated_on"):
        item.updated_on = timezone.localdate()
    if object_type == "task" and "status" in cleaned:
        item.completed_on = timezone.localdate() if item.status == "done" else None
    if object_type == "task":
        _validate_task_dependency(item)
    if object_type == "project":
        if "status" in cleaned and item.status == "done":
            item.progress = 100
        elif "progress" in cleaned:
            if item.progress == 100:
                item.status = "done"
            elif item.status == "done":
                item.status = "active"
    if object_type == "settings":
        _validate_settings_consistency(item)
    _validate_and_save(item)
    label = _record_label(object_type, item)
    _log_write(user, "updated", object_type, item.pk, label, cleaned)
    return {
        "ok": True,
        "operation": "updated",
        "object_type": object_type,
        "record": serialize_database_record(object_type, item),
        "references": _references(object_type, [item]),
    }


@transaction.atomic
def _delete_record(
    user,
    object_type,
    object_id,
    confirmed,
    delete_authorized,
    active_chat=None,
):
    if object_type not in DELETABLE_TYPES:
        raise DatabaseToolError("That record type cannot be deleted by the pet.", code="read_only")
    item = _get_owned_record(user, object_type, object_id)
    label = _record_label(object_type, item)
    if object_type == "chat" and active_chat is not None and item.pk == active_chat.pk:
        raise DatabaseToolError(
            "The active chat cannot delete itself. Switch to another chat before deleting this one.",
            code="active_chat",
        )
    settings_obj, _ = UserSettings.objects.get_or_create(user=user)
    if settings_obj.confirm_deletes and (not confirmed or not delete_authorized):
        return {
            "ok": False,
            "confirmation_required": True,
            "object_type": object_type,
            "object_id": str(item.pk),
            "label": label,
            "message": (
                f"Ask the user to explicitly confirm deleting the {object_type} ‘{label}’. "
                f"Do not claim it was deleted."
            ),
            "references": _references(object_type, [item]),
        }
    if not delete_authorized:
        raise DatabaseToolError(
            "The latest user message did not explicitly authorize this deletion.",
            code="write_not_authorized",
        )
    item_id = str(item.pk)
    item.delete()
    _log_write(user, "deleted", object_type, item_id, label)
    return {
        "ok": True,
        "operation": "deleted",
        "object_type": object_type,
        "object_id": item_id,
        "label": label,
        "references": [],
    }


def _parse_arguments(arguments):
    if isinstance(arguments, dict):
        return arguments
    if not isinstance(arguments, str):
        raise DatabaseToolError("Tool arguments must be a JSON object.")
    try:
        parsed = json.loads(arguments or "{}")
    except json.JSONDecodeError as exc:
        raise DatabaseToolError("Tool arguments were not valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise DatabaseToolError("Tool arguments must be a JSON object.")
    return parsed


def execute_database_tool(
    user,
    tool_name,
    arguments,
    *,
    allow_writes=False,
    delete_authorized=False,
    active_chat=None,
):
    """Run one allowlisted operation against only the signed-in user's records."""
    try:
        args = _parse_arguments(arguments)
        if tool_name == "workspace_overview":
            return {"ok": True, "overview": workspace_overview(user), "references": []}
        if tool_name == "query_records":
            return _query_records(user, args)
        if tool_name == "get_record":
            object_type = str(args.get("object_type") or "").strip().lower()
            item = _get_owned_record(user, object_type, args.get("object_id"))
            return {
                "ok": True,
                "object_type": object_type,
                "record": serialize_database_record(object_type, item),
                "references": _references(object_type, [item]),
            }
        if tool_name in {"create_record", "update_record", "delete_record"} and not allow_writes:
            raise DatabaseToolError(
                "The latest user message did not explicitly request a database change. Ask before writing.",
                code="write_not_authorized",
            )
        object_type = str(args.get("object_type") or "").strip().lower()
        if tool_name == "create_record":
            return _create_record(user, object_type, args.get("fields"))
        if tool_name == "update_record":
            return _update_record(user, object_type, args.get("object_id"), args.get("fields"))
        if tool_name == "delete_record":
            return _delete_record(
                user,
                object_type,
                args.get("object_id"),
                _as_bool(args.get("confirmed")),
                delete_authorized,
                active_chat,
            )
        raise DatabaseToolError("That database tool does not exist.", code="unknown_tool")
    except DatabaseToolError as exc:
        return {"ok": False, "error": {"code": exc.code, "message": str(exc)}, "references": []}
    except Exception:
        return {
            "ok": False,
            "error": {
                "code": "database_error",
                "message": "The database operation could not be completed safely.",
            },
            "references": [],
        }


def relevant_database_context(user, query):
    """Compact fallback context for providers that temporarily reject tool calling."""
    context = {"overview": workspace_overview(user), "relevant_records": []}
    terms = [
        term
        for term in re.findall(r"[A-Za-z0-9_-]{3,}", str(query or "").lower())
        if term not in {"about", "from", "have", "please", "show", "that", "the", "this", "what", "with"}
    ][:5]
    phrase = " ".join(terms)
    for object_type in ("project", "idea", "task", "skill", "annotation", "memory"):
        args = {"object_type": object_type, "query": phrase, "limit": 2} if phrase else {
            "object_type": object_type,
            "limit": 2,
        }
        result = _query_records(user, args)
        context["relevant_records"].extend(result["records"])
    return context


def database_object_cards(user, references):
    cards = []
    seen = set()
    for reference in references:
        object_type = str(reference.get("type") or "").lower()
        object_id = str(reference.get("id") or "")
        key = (object_type, object_id)
        if key in seen or object_type not in CARD_TYPES:
            continue
        try:
            item = _get_owned_record(user, object_type, object_id)
        except DatabaseToolError:
            continue
        cards.append(serialize_workspace_object(object_type, item))
        seen.add(key)
        if len(cards) >= 8:
            break
    return cards
