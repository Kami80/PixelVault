import re

from django.db.models import Q

from ..models import PetMemory


def retrieve_memories(user, query, limit=8):
    qs = PetMemory.objects.filter(owner=user)
    terms = [term for term in re.findall(r"[A-Za-z0-9_-]{3,}", str(query or ""))[:6]]
    if terms:
        lookup = Q()
        for term in terms:
            lookup |= Q(content__icontains=term)
        relevant = qs.filter(lookup)
        if relevant.exists():
            qs = relevant
    qs = qs.order_by("-importance", "-created_at")[:limit]
    return [m.content for m in qs]
