import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pet", "0004_petprofile_created_at_petprofile_current_state_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name="petmemory",
            old_name="created",
            new_name="created_at",
        ),
        migrations.AddField(
            model_name="petmemory",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pet_memories",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="petmemory",
            name="memory_type",
            field=models.CharField(
                choices=[
                    ("identity", "Identity"),
                    ("preference", "Preference"),
                    ("project", "Project"),
                    ("decision", "Decision"),
                    ("goal", "Goal"),
                    ("skill", "Skill"),
                    ("experience", "Experience"),
                    ("pattern", "Pattern"),
                    ("relationship", "Relationship"),
                    ("episode", "Episode"),
                ],
                default="experience",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="petmemory",
            name="importance",
            field=models.PositiveSmallIntegerField(
                default=50,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(100),
                ],
            ),
        ),
        migrations.AddField(
            model_name="petmemory",
            name="confidence",
            field=models.FloatField(
                default=0.8,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(1),
                ],
            ),
        ),
        migrations.AddField(
            model_name="petmemory",
            name="related_type",
            field=models.CharField(blank=True, default="", max_length=40),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="petmemory",
            name="related_id",
            field=models.CharField(blank=True, default="", max_length=120),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name="petmemory",
            options={"ordering": ["-importance", "-created_at"]},
        ),
        migrations.AlterField(
            model_name="petprofile",
            name="curiosity",
            field=models.PositiveSmallIntegerField(
                default=50,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(100),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="petprofile",
            name="energy",
            field=models.PositiveSmallIntegerField(
                default=100,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(100),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="petprofile",
            name="focus",
            field=models.PositiveSmallIntegerField(
                default=50,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(100),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="petprofile",
            name="happiness",
            field=models.PositiveSmallIntegerField(
                default=50,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(100),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="petprofile",
            name="level",
            field=models.PositiveIntegerField(
                default=1,
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
        migrations.AlterField(
            model_name="petprofile",
            name="xp",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
