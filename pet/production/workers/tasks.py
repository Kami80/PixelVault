try:
    from celery import shared_task
except ImportError:
    def shared_task(fn): return fn

@shared_task
def consolidate_pet_memory():
    return "memory consolidation complete"

@shared_task
def daily_pet_review():
    return "daily review complete"
