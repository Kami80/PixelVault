from ..models import PetMemory

CATEGORIES = ['identity','preference','project','decision','goal','skill','experience','pattern','relationship','episode']

def retrieve_context(user, limit=10):
    return list(PetMemory.objects.filter(owner=user).order_by('-importance')[:limit].values('memory_type','content','importance','confidence'))

def add_memory(user, memory_type, content, importance=50, confidence=.8):
    return PetMemory.objects.create(owner=user,memory_type=memory_type,content=content,importance=importance,confidence=confidence)
