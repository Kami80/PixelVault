from django.utils import timezone

from workspace.models import Idea, Project, Skill, Task, UserSettings


def seed_demo_workspace(user):
    today = timezone.localdate()
    settings, _ = UserSettings.objects.get_or_create(user=user)
    project, _ = Project.objects.get_or_create(
        owner=user,
        title="PixelVault Django",
        defaults={
            "description": "Local productivity OS rebuilt with Django, SQLite, server-backed reports and filesystem browsing.",
            "tags": ["django", "local", "productivity"],
            "status": "active",
            "is_web": True,
            "pinned": True,
            "progress": 15,
            "goal": "Run the complete PixelVault workspace from a proper Django backend.",
            "next_milestone": "Customize your workspace and connect the first real project folder.",
        },
    )
    Idea.objects.get_or_create(
        owner=user,
        title="Agent Context Pack",
        defaults={
            "description": "Generate concise project context from selected projects and skills.",
            "content_type": "prompt",
            "status": "exploring",
            "priority": "high",
            "tags": ["agents", "prompt", "workflow"],
            "pinned": True,
            "next_action": "Define the first export format.",
        },
    )
    Task.objects.get_or_create(
        owner=user,
        title="Explore the Django dashboard",
        defaults={
            "description": "Open each module, review settings, and configure your first project.",
            "project": project,
            "status": "doing",
            "priority": "high",
            "scheduled_date": today,
            "due_date": today,
            "duration_minutes": 45,
            "tags": ["setup"],
            "pinned": True,
        },
    )
    Skill.objects.get_or_create(
        owner=user,
        name="Retro UI Builder",
        defaults={
            "description": "Build vibrant pixel-inspired interfaces while preserving hierarchy, readability and accessibility.",
            "category": "Design",
            "version": "1.0.0",
            "tags": ["ui", "retro", "css"],
            "agents": ["Coding Agent"],
            "pinned": True,
            "filename": "retro-ui-builder.skill.md",
            "content": "# Retro UI Builder\n\n## Purpose\nCreate pixel-inspired interfaces with clear hierarchy and accessible controls.\n\n## Rules\n- Keep body text readable.\n- Use retro styling as decoration, not friction.\n- Respect reduced-motion preferences.\n- Keep touch targets comfortably large.\n",
        },
    )
    settings.skill_selected = Skill.objects.filter(owner=user).values_list("id", flat=True).first() or ""
    settings.save(update_fields=["skill_selected", "updated_at"])
