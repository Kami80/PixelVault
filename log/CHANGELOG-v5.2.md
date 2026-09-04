# PixelVault V5.2 — GitHub Pages Projects

## Added

- Dedicated `github_pages_url` field on Django `Project`.
- Migration `workspace/migrations/0002_project_github_pages_url.py`.
- GitHub Pages URL field in the project create/edit form.
- LIVE badge on project cards when a Pages URL exists.
- One-click **LIVE SITE** action on project cards.
- One-click **GITHUB PAGES** action in the project workspace.
- Live URL displayed in project workspace metadata.
- `launchProject()` now falls back to GitHub Pages before Django static preview.
- GitHub Pages URL is included in workspace JSON backup/import automatically.

## Compatibility

Existing V5 and V5.1 projects continue to work. After copying these updated files over a V5 installation, run:

```bash
python manage.py migrate
```
