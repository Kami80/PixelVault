from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def idea_id():
    return make_id("idea")


def project_id():
    return make_id("project")


def task_id():
    return make_id("task")


def skill_id():
    return make_id("skill")


def annotation_id():
    return make_id("ann")


class UserSettings(models.Model):
    THEME_CHOICES = [
        ("pixel-night", "Pixel Night"),
        ("neon-cyan", "Neon Circuit"),
        ("synthwave", "Synth Sunset"),
        ("terminal", "Terminal Green"),
        ("amber-crt", "Amber CRT"),
        ("paper-light", "Pixel Paper"),
        ("candy-light", "Candy Desktop"),
    ]
    ACCENT_CHOICES = [(v, v.title()) for v in ["pink", "cyan", "lime", "yellow", "violet", "orange"]]
    TEXT_SIZE_CHOICES = [("normal", "Normal"), ("large", "Large"), ("xlarge", "Extra Large")]
    DENSITY_CHOICES = [("comfortable", "Comfortable"), ("compact", "Compact")]
    WEEK_CHOICES = [("monday", "Monday"), ("sunday", "Sunday")]
    PLANNER_CHOICES = [("daily", "Daily"), ("weekly", "Weekly"), ("calendar", "Calendar")]
    PAGE_CHOICES = [(x, x.title()) for x in ["home", "ideas", "projects", "tasks", "planner", "skills", "reports", "annotations", "settings"]]
    HIGHLIGHT_CHOICES = [(x, x.title()) for x in ["yellow", "pink", "cyan", "lime"]]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pixelvault_settings")
    display_name = models.CharField(max_length=60, default="Local Builder")
    role = models.CharField(max_length=80, default="Maker / Builder")
    workspace_name = models.CharField(max_length=60, default="PixelVault")
    social_handle = models.CharField(max_length=60, blank=True)
    bio = models.CharField(max_length=280, blank=True)
    avatar = models.CharField(max_length=64, default="mascot-cat.webp")

    theme = models.CharField(max_length=32, choices=THEME_CHOICES, default="pixel-night")
    accent = models.CharField(max_length=16, choices=ACCENT_CHOICES, default="pink")
    density = models.CharField(max_length=16, choices=DENSITY_CHOICES, default="comfortable")
    text_size = models.CharField(max_length=16, choices=TEXT_SIZE_CHOICES, default="large")
    reduce_motion = models.BooleanField(default=False)
    show_grid = models.BooleanField(default=True)
    show_mascots = models.BooleanField(default=True)
    confirm_deletes = models.BooleanField(default=True)
    high_contrast = models.BooleanField(default=False)
    large_targets = models.BooleanField(default=False)

    landing_page = models.CharField(max_length=20, choices=PAGE_CHOICES, default="home")
    planner_default_view = models.CharField(max_length=16, choices=PLANNER_CHOICES, default="weekly")
    planner_view = models.CharField(max_length=16, choices=PLANNER_CHOICES, default="weekly")
    planner_anchor = models.DateField(default=timezone.localdate)
    week_start = models.CharField(max_length=10, choices=WEEK_CHOICES, default="monday")
    workday_start = models.PositiveSmallIntegerField(default=7, validators=[MaxValueValidator(23)])
    workday_end = models.PositiveSmallIntegerField(default=22, validators=[MinValueValidator(1), MaxValueValidator(24)])
    default_task_duration = models.PositiveIntegerField(default=45, validators=[MinValueValidator(5), MaxValueValidator(1440)])
    planner_snap_minutes = models.PositiveSmallIntegerField(default=15, validators=[MinValueValidator(15), MaxValueValidator(60)])
    planner_hour_px = models.PositiveSmallIntegerField(default=96, validators=[MinValueValidator(64), MaxValueValidator(144)])

    default_highlight = models.CharField(max_length=16, choices=HIGHLIGHT_CHOICES, default="yellow")
    show_highlights = models.BooleanField(default=True)
    signature = models.CharField(max_length=80, blank=True)
    skill_selected = models.CharField(max_length=64, blank=True)

    # Optional local filesystem boundary. When set, project folder browsing is restricted to this root.
    workspace_root = models.CharField(max_length=1024, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} · {self.workspace_name}"

    def normalized_workspace_root(self):
        if not self.workspace_root:
            return None
        try:
            return Path(self.workspace_root).expanduser().resolve()
        except (OSError, RuntimeError):
            return None


class Idea(models.Model):
    STATUS_CHOICES = [(x, x.title()) for x in ["inbox", "exploring", "ready", "building"]]
    PRIORITY_CHOICES = [(x, x.title()) for x in ["low", "medium", "high"]]
    CONTENT_CHOICES = [(x, x.title()) for x in ["note", "prompt", "webpage", "reference"]]

    id = models.CharField(primary_key=True, max_length=64, default=idea_id, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pixelvault_ideas")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    content_type = models.CharField(max_length=20, choices=CONTENT_CHOICES, default="note")
    content = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="inbox")
    priority = models.CharField(max_length=12, choices=PRIORITY_CHOICES, default="medium")
    goal = models.TextField(blank=True)
    audience = models.CharField(max_length=180, blank=True)
    source_url = models.URLField(max_length=1000, blank=True)
    live_site_url = models.URLField(max_length=1000, blank=True)
    tags = models.JSONField(default=list, blank=True)
    project = models.ForeignKey("Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="ideas")
    next_action = models.CharField(max_length=500, blank=True)
    pinned = models.BooleanField(default=False)
    created_on = models.DateField(default=timezone.localdate)
    updated_on = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["-pinned", "-updated_on", "title"]

    def __str__(self):
        return self.title


class Project(models.Model):
    STATUS_CHOICES = [(x, x.title()) for x in ["active", "paused", "done"]]

    id = models.CharField(primary_key=True, max_length=64, default=project_id, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pixelvault_projects")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    progress = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    local_path = models.CharField(max_length=1024, blank=True)
    launch_url = models.URLField(max_length=1000, blank=True)
    repository_url = models.URLField(max_length=1000, blank=True)
    github_pages_url = models.URLField(max_length=1000, blank=True)
    tech_stack = models.JSONField(default=list, blank=True)
    is_web = models.BooleanField(default=False)
    target_date = models.DateField(null=True, blank=True)
    goal = models.TextField(blank=True)
    next_milestone = models.CharField(max_length=500, blank=True)
    notes = models.TextField(blank=True)
    pinned = models.BooleanField(default=False)
    created_on = models.DateField(default=timezone.localdate)
    updated_on = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["-pinned", "-updated_on", "title"]

    def __str__(self):
        return self.title


class Task(models.Model):
    STATUS_CHOICES = [(x, x.title()) for x in ["todo", "doing", "done"]]
    PRIORITY_CHOICES = [(x, x.title()) for x in ["high", "medium", "low"]]
    ENERGY_CHOICES = [(x, x.title()) for x in ["low", "medium", "high"]]
    RECURRENCE_CHOICES = [(x, x.title()) for x in ["none", "daily", "weekly", "monthly"]]

    id = models.CharField(primary_key=True, max_length=64, default=task_id, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pixelvault_tasks")
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="todo")
    priority = models.CharField(max_length=12, choices=PRIORITY_CHOICES, default="medium")
    task_type = models.CharField(max_length=40, default="development", blank=True)
    energy = models.CharField(max_length=12, choices=ENERGY_CHOICES, default="medium")
    scheduled_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=45, validators=[MaxValueValidator(1440)])
    recurrence = models.CharField(max_length=12, choices=RECURRENCE_CHOICES, default="none")
    depends_on = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="dependent_tasks")
    subtasks = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    pinned = models.BooleanField(default=False)
    completed_on = models.DateField(null=True, blank=True)
    created_on = models.DateField(default=timezone.localdate)
    updated_on = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["status", "scheduled_date", "start_time", "-pinned", "title"]

    def __str__(self):
        return self.title


class Skill(models.Model):
    id = models.CharField(primary_key=True, max_length=64, default=skill_id, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pixelvault_skills")
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, default="General")
    version = models.CharField(max_length=40, default="1.0.0")
    source_url = models.URLField(max_length=1000, blank=True)
    tags = models.JSONField(default=list, blank=True)
    agents = models.JSONField(default=list, blank=True)
    use_cases = models.JSONField(default=list, blank=True)
    filename = models.CharField(max_length=255, default="skill.md")
    content = models.TextField(blank=True)
    attached_file = models.FileField(upload_to="skills/%Y/%m/", blank=True)
    pinned = models.BooleanField(default=False)
    created_on = models.DateField(default=timezone.localdate)
    updated_on = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["-pinned", "category", "name"]

    def __str__(self):
        return self.name


class Annotation(models.Model):
    COLOR_CHOICES = [(x, x.title()) for x in ["yellow", "pink", "cyan", "lime"]]

    id = models.CharField(primary_key=True, max_length=64, default=annotation_id, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pixelvault_annotations")
    page_key = models.CharField(max_length=40)
    selected_text = models.TextField()
    prefix = models.TextField(blank=True)
    suffix = models.TextField(blank=True)
    color = models.CharField(max_length=16, choices=COLOR_CHOICES, default="yellow")
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.page_key}: {self.selected_text[:50]}"


class Activity(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pixelvault_activity")
    verb = models.CharField(max_length=80)
    entity_type = models.CharField(max_length=40, blank=True)
    entity_id = models.CharField(max_length=64, blank=True)
    label = models.CharField(max_length=250, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.verb} {self.label}".strip()
