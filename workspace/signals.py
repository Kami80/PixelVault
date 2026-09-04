from django.db.models.signals import post_delete
from django.dispatch import receiver

from workspace.models import Skill


@receiver(post_delete, sender=Skill)
def delete_skill_attachment(sender, instance, **kwargs):
    if instance.attached_file:
        try:
            instance.attached_file.delete(save=False)
        except Exception:
            pass
