import re

from django.db.models import Q

from workspace.models import Idea, Project, Skill, Task
from .objects import serialize_workspace_object


def search_objects(user, query):
    stop_words = {"about", "could", "find", "please", "show", "that", "the", "this", "what", "with", "would"}
    terms = [
        term for term in re.findall(r"[A-Za-z0-9_-]{3,}", str(query or "").lower())
        if term not in stop_words
    ][:6]
    if not terms:
        return []

    result = []
    for model, object_type, label_field in [
        (Project, "project", "title"),
        (Idea, "idea", "title"),
        (Task, "task", "title"),
        (Skill, "skill", "name"),
    ]:
        lookup = Q()
        for term in terms:
            lookup |= Q(**{f"{label_field}__icontains": term}) | Q(description__icontains=term)
        for item in model.objects.filter(owner=user).filter(lookup).order_by("-updated_on")[:5]:
            result.append(serialize_workspace_object(object_type, item))
    return result[:10]
