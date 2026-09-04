from django.urls import path
from workspace import views

urlpatterns = [
    path("", views.app_view, name="app"),
    path("api/state/", views.api_state, name="api_state"),
    path("api/health/", views.api_health, name="api_health"),
    path("api/backup/export/", views.backup_export, name="backup_export"),
    path("api/skills/<str:skill_id>/upload/", views.skill_upload, name="skill_upload"),
    path("api/skills/<str:skill_id>/download/", views.skill_download, name="skill_download"),
    path("api/skills/<str:skill_id>/write/", views.skill_write, name="skill_write"),
    path("api/projects/<str:project_id>/tree/", views.project_tree, name="project_tree"),
    path("api/projects/<str:project_id>/file/", views.project_file, name="project_file"),
    path("preview/<str:project_id>/", views.project_preview, name="project_preview_root"),
    path("preview/<str:project_id>/<path:subpath>", views.project_preview, name="project_preview"),
    path("reports/social.png", views.report_png, name="report_png"),
    path("reports/report.pdf", views.report_pdf, name="report_pdf"),
]
