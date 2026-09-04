from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workspace", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="github_pages_url",
            field=models.URLField(blank=True, max_length=1000),
        ),
    ]
