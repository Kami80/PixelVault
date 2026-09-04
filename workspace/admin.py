from django.contrib import admin
from workspace.models import Activity, Annotation, Idea, Project, Skill, Task, UserSettings


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "workspace_name", "theme", "updated_at")
    search_fields = ("user__username", "workspace_name", "display_name")


@admin.register(Idea)
class IdeaAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "status", "priority", "pinned", "updated_on")
    list_filter = ("status", "priority", "pinned")
    search_fields = ("title", "description", "content", "source_url", "live_site_url")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "status", "progress", "is_web", "pinned")
    list_filter = ("status", "is_web", "pinned")
    search_fields = ("title", "description", "local_path", "repository_url", "github_pages_url")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "status", "priority", "scheduled_date", "due_date", "pinned")
    list_filter = ("status", "priority", "recurrence", "pinned")
    search_fields = ("title", "description", "notes")


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "category", "version", "pinned", "updated_on")
    list_filter = ("category", "pinned")
    search_fields = ("name", "description", "content")


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    list_display = ("page_key", "owner", "color", "created_at")
    list_filter = ("page_key", "color")
    search_fields = ("selected_text", "comment")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("created_at", "owner", "verb", "entity_type", "label")
    list_filter = ("verb", "entity_type")
    search_fields = ("label",)
