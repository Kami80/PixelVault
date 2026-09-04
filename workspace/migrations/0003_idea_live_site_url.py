from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workspace", "0002_project_github_pages_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="idea",
            name="live_site_url",
            field=models.URLField(blank=True, max_length=1000),
        ),
    ]
