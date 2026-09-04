# Upgrade PixelVault V5 to V5.2.2

Copy every file/folder in this package over the matching paths in your existing PixelVault V5 project.

Then run:

```bash
python manage.py migrate
```

The included migrations add:

- optional GitHub Pages URL for Projects
- optional Live Site URL for Ideas

Existing project, idea, task, planner and skill data is preserved.

## V5.3 Planner update
V5.3 adds migration `0004_usersettings_planner_timeline_preferences.py` so snap and zoom preferences persist. Replace the updated files, run `python manage.py migrate`, then restart Django. The Planner now renders task blocks according to `duration`, includes 15/30/60-minute snap controls, zoom, overlap handling, task duplication and scheduling quick actions.
