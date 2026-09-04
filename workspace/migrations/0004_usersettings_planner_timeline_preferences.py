from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("workspace", "0003_idea_live_site_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersettings",
            name="planner_hour_px",
            field=models.PositiveSmallIntegerField(default=96, validators=[django.core.validators.MinValueValidator(64), django.core.validators.MaxValueValidator(144)]),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="planner_snap_minutes",
            field=models.PositiveSmallIntegerField(default=15, validators=[django.core.validators.MinValueValidator(15), django.core.validators.MaxValueValidator(60)]),
        ),
    ]
