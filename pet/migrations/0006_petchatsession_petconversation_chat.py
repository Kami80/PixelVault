import uuid

import django.db.models.deletion
from django.db import migrations, models


def preserve_existing_conversations(apps, schema_editor):
    PetChatSession = apps.get_model("pet", "PetChatSession")
    PetConversation = apps.get_model("pet", "PetConversation")
    PetProfile = apps.get_model("pet", "PetProfile")

    for pet in PetProfile.objects.all().iterator():
        conversations = PetConversation.objects.filter(pet_id=pet.pk, chat_id__isnull=True)
        if not conversations.exists():
            continue
        chat = PetChatSession.objects.create(pet_id=pet.pk, title="Previous chat")
        conversations.update(chat_id=chat.pk)
        oldest = conversations.order_by("created_at").values_list("created_at", flat=True).first()
        newest = conversations.order_by("-created_at").values_list("created_at", flat=True).first()
        PetChatSession.objects.filter(pk=chat.pk).update(
            created_at=oldest or chat.created_at,
            updated_at=newest or chat.updated_at,
        )


class Migration(migrations.Migration):
    dependencies = [("pet", "0005_restore_pet_memory_fields_and_profile_constraints")]

    operations = [
        migrations.CreateModel(
            name="PetChatSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(default="New chat", max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "pet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chats",
                        to="pet.petprofile",
                    ),
                ),
            ],
            options={"ordering": ["-updated_at", "-created_at"]},
        ),
        migrations.AddField(
            model_name="petconversation",
            name="chat",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="conversations",
                to="pet.petchatsession",
            ),
        ),
        migrations.RunPython(preserve_existing_conversations, migrations.RunPython.noop),
    ]
