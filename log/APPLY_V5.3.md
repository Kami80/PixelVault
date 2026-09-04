# Apply PixelVault V5.3

Copy these files over your current PixelVault V5.2.2/V5.2.1 project while preserving the folder structure.

Then run:

```bash
python manage.py migrate
python manage.py runserver
```

The migration only stores the Planner snap interval and timeline zoom preferences. Existing ideas, projects and tasks are preserved.
