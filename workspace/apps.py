from django.apps import AppConfig


class WorkspaceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "workspace"
    verbose_name = "PixelVault Workspace"

    def ready(self):
        from workspace import signals  # noqa: F401
