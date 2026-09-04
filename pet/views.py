import json
import logging
import re
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .agent.brain import run_pet
from .agent.nvidia import is_nemotron_configured, nemotron_model
from .agent.objects import (
    WorkspaceObjectError,
    WorkspaceObjectNotFound,
    perform_object_action,
    serialize_workspace_object,
)
from .models import PetChatSession, PetConversation, PetMemory, PetProfile
from workspace.models import Idea, Project, Skill, Task

logger = logging.getLogger(__name__)
OBJECT_REFERENCE = re.compile(r"\[(project|idea|task|skill):([A-Za-z0-9_-]{1,128})\]", re.IGNORECASE)


def _ensure_legacy_chat(pet):
    unassigned = pet.conversations.filter(chat__isnull=True)
    if not unassigned.exists():
        return None
    chat = pet.chats.filter(title="Previous chat").first()
    if chat is None:
        chat = PetChatSession.objects.create(pet=pet, title="Previous chat")
    unassigned.update(chat=chat)
    newest = chat.conversations.order_by("-created_at").values_list("created_at", flat=True).first()
    if newest:
        PetChatSession.objects.filter(pk=chat.pk).update(updated_at=newest)
        chat.updated_at = newest
    return chat


def _active_chat(pet, chat_id=""):
    _ensure_legacy_chat(pet)
    if chat_id:
        try:
            requested = pet.chats.filter(pk=chat_id).first()
        except (ValidationError, ValueError):
            requested = None
        if requested is not None:
            return requested
    return pet.chats.first() or PetChatSession.objects.create(pet=pet)


def _chat_title(message):
    title = re.sub(r"\s+", " ", str(message or "")).strip()
    title = re.sub(
        r"^(?:please\s+)?(?:add|create|save|capture)\s+(?:an?\s+)?"
        r"(?:idea|task|project)\s*[:—-]?\s*",
        "",
        title,
        flags=re.IGNORECASE,
    ) or title
    title = re.split(r"(?<=[.!?])\s+", title, maxsplit=1)[0].strip(" .!?\t\r\n")
    if len(title) > 64:
        title = title[:65].rsplit(" ", 1)[0].rstrip(" ,:;.-") or title[:64]
    if title and title[0].islower():
        title = title[0].upper() + title[1:]
    return title or "New chat"


def _conversation_cards(user, conversations):
    references = {"project": set(), "idea": set(), "task": set(), "skill": set()}
    for conversation in conversations:
        for match in OBJECT_REFERENCE.finditer(conversation.pet_response or ""):
            references[match.group(1).lower()].add(match.group(2))

    object_index = {}
    model_map = {
        "project": (Project, "title"),
        "idea": (Idea, "title"),
        "task": (Task, "title"),
        "skill": (Skill, "name"),
    }
    for object_type, (model, label_field) in model_map.items():
        queryset = model.objects.filter(owner=user, pk__in=references[object_type])
        if object_type in {"idea", "task"}:
            queryset = queryset.select_related("project")
        for item in queryset:
            key = f"{object_type}:{item.pk}"
            object_index[key] = serialize_workspace_object(object_type, item)
            object_index[key]["url"] = f"{reverse('app')}?{urlencode({'open': key})}"

    cards = []
    for conversation in conversations:
        links = []
        seen = set()

        def replace_reference(match):
            key = f"{match.group(1).lower()}:{match.group(2)}"
            if key in object_index and key not in seen:
                links.append(object_index[key])
                seen.add(key)
            return ""

        response = OBJECT_REFERENCE.sub(replace_reference, conversation.pet_response or "")
        response = re.sub(r"\s+([.,!?;:])", r"\1", response)
        response = re.sub(r"[ \t]{2,}", " ", response).strip()
        cards.append(
            {
                "user_message": conversation.user_message,
                "pet_response": response or "I’m ready for the next move.",
                "emotion": conversation.emotion,
                "objects": links,
            }
        )
    return cards


@login_required
def pet_page(request):
    pet, _ = PetProfile.objects.get_or_create(owner=request.user)
    active_chat = _active_chat(pet, request.GET.get("chat", ""))
    conversations = list(active_chat.conversations.all()[:50])
    chat_sessions = list(pet.chats.annotate(message_count=Count("conversations")))
    return render(
        request,
        "pet/pet.html",
        {
            "pet": pet,
            "active_chat": active_chat,
            "chat_sessions": chat_sessions,
            "conversations": _conversation_cards(request.user, conversations),
            "memories": PetMemory.objects.filter(owner=request.user)[:8],
            "remote_ai_enabled": is_nemotron_configured(),
            "remote_ai_model": nemotron_model(),
            "pv_version": settings.PIXELVAULT_VERSION,
        },
    )


@login_required
@require_POST
def pet_chat_new(request):
    pet, _ = PetProfile.objects.get_or_create(owner=request.user)
    chat = PetChatSession.objects.create(pet=pet)
    return redirect(f"{reverse('pet')}?{urlencode({'chat': chat.pk})}")


@login_required
@require_GET
def pet_memory(request):
    memories = [
        {
            "id": memory.pk,
            "memoryType": memory.memory_type,
            "content": memory.content,
            "importance": memory.importance,
            "confidence": memory.confidence,
            "createdAt": memory.created_at.isoformat(),
        }
        for memory in PetMemory.objects.filter(owner=request.user)[:50]
    ]
    return JsonResponse({"memories": memories})


@login_required
@require_POST
def pet_chat(request):
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Send a valid JSON request."}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)

    message = str(data.get("message") or "").strip()
    if not message:
        return JsonResponse({"error": "Write a message for your companion."}, status=400)
    if len(message) > 1_000:
        return JsonResponse({"error": "Messages are limited to 1,000 characters."}, status=400)

    pet, _ = PetProfile.objects.get_or_create(owner=request.user)
    chat_id = str(data.get("chatId") or "").strip()
    if chat_id:
        try:
            chat = pet.chats.filter(pk=chat_id).first()
        except (ValidationError, ValueError):
            chat = None
        if chat is None:
            return JsonResponse({"error": "That chat does not exist."}, status=404)
    else:
        chat = _active_chat(pet)
    try:
        result = run_pet(request.user, message, chat=chat)
    except Exception:
        logger.exception("Pet agent request failed for user_id=%s", request.user.pk)
        result = {
            "message": "I hit a temporary problem, but your workspace is safe. Please try again.",
            "emotion": "concerned",
            "objects": [],
        }

    reply = str(result.get("message") or "I am ready.")
    emotion = str(result.get("emotion") or "focused")[:50]
    conversation = PetConversation.objects.create(
        pet=pet,
        chat=chat,
        user_message=message,
        pet_response=reply,
        emotion=emotion,
    )
    pet.current_state = emotion
    pet.save(update_fields=["current_state"])
    chat.refresh_from_db(fields=["title"])
    update_fields = ["updated_at"]
    if chat.title == "New chat":
        chat.title = _chat_title(message)
        update_fields.append("title")
    chat.updated_at = timezone.now()
    chat.save(update_fields=update_fields)
    return JsonResponse(
        {
            "message": reply,
            "emotion": emotion,
            "objects": result.get("objects") if isinstance(result.get("objects"), list) else [],
            "action": result.get("action") if isinstance(result.get("action"), dict) else None,
            "ai": result.get("ai") if isinstance(result.get("ai"), dict) else None,
            "chatId": str(chat.pk),
            "chatTitle": chat.title,
            "chatMessageCount": chat.conversations.count(),
            "conversationId": conversation.pk,
        }
    )


@login_required
@require_POST
def pet_object_action(request):
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Send a valid JSON request."}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)

    object_type = str(data.get("type") or "").strip().lower()
    object_id = str(data.get("id") or "").strip()
    action = str(data.get("action") or "").strip().lower()
    value = str(data.get("value") or "").strip()
    if not object_type or not object_id or not action:
        return JsonResponse({"error": "Object type, id, and action are required."}, status=400)
    if len(value) > 500:
        return JsonResponse({"error": "Action values are limited to 500 characters."}, status=400)
    try:
        return JsonResponse(perform_object_action(request.user, object_type, object_id, action, value))
    except WorkspaceObjectNotFound as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    except WorkspaceObjectError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
