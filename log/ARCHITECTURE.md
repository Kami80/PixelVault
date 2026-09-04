# PixelVault Django Architecture

## Design goal

The original PixelVault UI remains a fast single-page-like interface, but browser-only persistence has been removed. Django now owns authentication, validation, persistence, filesystem access, uploads, backups, and report generation.

## Layers

### 1. Presentation

- `templates/pixelvault/app.html` — primary workspace shell
- `templates/pixelvault/setup.html` — first-run setup
- `templates/registration/login.html` — authentication
- `static/pixelvault/css/styles.css` — full retro pixel UI + themes + accessibility/readability overrides
- `static/pixelvault/js/app.js` — interaction layer, planner drag/drop, forms, highlights, search, and API synchronization

### 2. Domain models

`workspace/models.py` contains normalized per-user models:

- `UserSettings`
- `Idea`
- `Project`
- `Task`
- `Skill`
- `Annotation`
- `Activity`

Project/task/idea relationships use real Django foreign keys. Task dependencies use a self-referencing foreign key. Lists such as tags, agents, use cases, subtasks, and tech stacks use JSON fields.

### 3. Persistence bridge

`workspace/services/state.py` converts normalized models into the compact state shape used by the existing UI and applies incoming state transactionally.

The primary workspace sync endpoint is:

```text
GET /api/state/
PUT /api/state/
```

A state PUT is wrapped in a database transaction. Objects are always scoped to the authenticated owner.

### 4. Filesystem service

`workspace/services/filesystem.py` performs server-side project browsing.

Security boundaries:

1. The configured project path is resolved to a canonical absolute path.
2. If `workspace_root` is configured, project roots must stay inside it.
3. Every requested subpath must stay inside its project root.
4. File previews are limited to supported text formats and 2 MB.
5. Directory responses are lazy/paged at a maximum of 500 direct children per request.

Static web previews additionally block dotfiles and sensitive server/config extensions.

### 5. Skills files

Skill Markdown text lives in the database. A `FileField` optionally stores the attached source file under `media/skills/`. A post-delete signal removes an attached file when its skill is deleted.

### 6. Reports

`workspace/services/reporting.py` queries real task/project rows and creates:

- 1080×1350 PNG social cards with Pillow
- multi-page A4 PDF reports with ReportLab

The report service supports daily, weekly, monthly, full, public-safe, and showcase modes.

### 7. Authentication

The first empty database uses `/setup/` to create its initial owner. Standard Django authentication protects the application and every data endpoint.

## API map

```text
GET|PUT /api/state/
GET     /api/health/
GET     /api/backup/export/

POST    /api/skills/<id>/upload/
POST    /api/skills/<id>/write/
GET     /api/skills/<id>/download/

GET     /api/projects/<id>/tree/?path=...
GET     /api/projects/<id>/file/?path=...
GET     /preview/<project-id>/...

GET     /reports/social.png
GET     /reports/report.pdf
```

## Why the UI still uses a state endpoint

PixelVault has many tightly connected drag/drop and cross-module interactions. Keeping a short-lived in-memory client state preserves immediate UI feedback while Django remains the source of truth. The state endpoint translates that client shape into normalized relational models inside one transaction.

This also means the UI can later move module-by-module to granular REST/HTMX endpoints without a database migration.

## Data ownership

Every user-owned model includes an `owner` relation. State upserts reject identifier collisions owned by another user. Filesystem, skill-file, backup, and report endpoints all require authentication and query by the current owner.
