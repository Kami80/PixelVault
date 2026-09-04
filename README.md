# PixelVault

PixelVault is a local-first Django productivity workspace for ideas, projects, tasks, planning, reusable agent skills, reports, annotations, and an optional AI pet companion.

## Quick start (Windows PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements_sqlite.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/setup/> on the first run. Later visits use the normal login page.

If this folder was copied from another computer, recreate `.venv`; virtual environments contain machine-specific interpreter paths and are not portable.

## Configuration

PixelVault reads `.env` automatically. The local defaults use SQLite and debug mode. Before any public deployment:

- generate a strong `PIXELVAULT_SECRET_KEY`;
- set `PIXELVAULT_DEBUG=0`;
- configure `PIXELVAULT_ALLOWED_HOSTS` and trusted origins;
- serve the app behind HTTPS with secure cookies;
- keep `NVIDIA_API_KEY` only in `.env` or a secrets manager.

The pet chat works without an NVIDIA key by returning a local workspace-aware fallback. Add a key only when remote model responses are wanted. With remote AI enabled, the pet can request relevant records from the signed-in account and send those tool results to the configured NVIDIA endpoint to answer the user. Authentication tables, sessions, API keys, raw SQL, workspace roots, and project local paths are not exposed through these tools.

Database access is allowlisted and account-scoped. Reads cover workspace objects, annotations, memories, safe settings, activity, the pet profile, and saved chat messages. Writes require an explicit user request, every agent write is recorded in Activity, and destructive actions require confirmation by default. `PET_AGENT_THINKING=0` keeps structured tool calls concise; set it to `1` only if longer model reasoning is preferred over response speed.

## Verification

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Project-folder browsing is read-only, remains inside each configured project root, and hides dotfiles and common credential/database files. Static project previews run in a sandboxed document origin.
