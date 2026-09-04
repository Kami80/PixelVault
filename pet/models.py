import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class PetProfile(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pet_profile",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=50, default="Voxie")
    level = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    xp = models.PositiveIntegerField(default=0)
    happiness = models.PositiveSmallIntegerField(
        default=50, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    energy = models.PositiveSmallIntegerField(
        default=100, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    curiosity = models.PositiveSmallIntegerField(
        default=50, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    focus = models.PositiveSmallIntegerField(
        default=50, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    current_state = models.CharField(max_length=50, default="idle")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        owner = self.owner.get_username() if self.owner_id else "unassigned"
        return f"{self.name} ({owner})"


class PetMemory(models.Model):
    MEMORY_TYPES = [
        ("identity", "Identity"),
        ("preference", "Preference"),
        ("project", "Project"),
        ("decision", "Decision"),
        ("goal", "Goal"),
        ("skill", "Skill"),
        ("experience", "Experience"),
        ("pattern", "Pattern"),
        ("relationship", "Relationship"),
        ("episode", "Episode"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pet_memories",
        null=True,
        blank=True,
    )
    memory_type = models.CharField(max_length=30, choices=MEMORY_TYPES, default="experience")
    content = models.TextField()
    importance = models.PositiveSmallIntegerField(
        default=50, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    confidence = models.FloatField(
        default=0.8, validators=[MinValueValidator(0), MaxValueValidator(1)]
    )
    related_type = models.CharField(max_length=40, blank=True)
    related_id = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-importance", "-created_at"]

    def __str__(self):
        return self.content[:60]


class PetAbility(models.Model):
    name = models.CharField(max_length=100)
    unlocked = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class PetChatSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pet = models.ForeignKey(PetProfile, on_delete=models.CASCADE, related_name="chats")
    title = models.CharField(max_length=120, default="New chat")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]

    def __str__(self):
        return self.title


class PetConversation(models.Model):
    pet = models.ForeignKey(
        PetProfile,
        on_delete=models.CASCADE,
        related_name="conversations",
        null=True,
        blank=True,
    )
    chat = models.ForeignKey(
        PetChatSession,
        on_delete=models.CASCADE,
        related_name="conversations",
        null=True,
        blank=True,
    )
    user_message = models.TextField()
    pet_response = models.TextField()
    emotion = models.CharField(max_length=50, default="happy")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.user_message[:50]
