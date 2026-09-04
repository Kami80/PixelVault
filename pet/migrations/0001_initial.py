from django.db import migrations,models
import django.db.models.deletion
from django.conf import settings
class Migration(migrations.Migration):
 initial=True
 dependencies=[('auth','0012_alter_user_first_name_max_length')]
 operations=[
 migrations.CreateModel(name='PetProfile',fields=[('id',models.BigAutoField(primary_key=True,serialize=False)),('name',models.CharField(default='Pixel',max_length=80)),('species',models.CharField(default='Pixel Spirit',max_length=80)),('mood',models.CharField(default='idle',max_length=40)),('level',models.PositiveIntegerField(default=1)),('xp',models.PositiveIntegerField(default=0)),('personality',models.CharField(default='friendly',max_length=40)),('created_at',models.DateTimeField()),('owner',models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,to=settings.AUTH_USER_MODEL))]),
 migrations.CreateModel(name='PetMemory',fields=[('id',models.BigAutoField(primary_key=True,serialize=False)),('memory_type',models.CharField(default='experience',max_length=30)),('content',models.TextField()),('importance',models.PositiveIntegerField(default=50)),('confidence',models.FloatField(default=0.8)),('related_type',models.CharField(blank=True,max_length=40)),('related_id',models.CharField(blank=True,max_length=120)),('created_at',models.DateTimeField(auto_now_add=True)),('owner',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,to=settings.AUTH_USER_MODEL))]),
 migrations.CreateModel(name='PetConversation',fields=[('id',models.BigAutoField(primary_key=True,serialize=False)),('role',models.CharField(max_length=20)),('content',models.TextField()),('created_at',models.DateTimeField(auto_now_add=True)),('owner',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,to=settings.AUTH_USER_MODEL))]),
 migrations.CreateModel(name='PetAction',fields=[('id',models.BigAutoField(primary_key=True,serialize=False)),('action',models.CharField(max_length=80)),('payload',models.JSONField(default=dict)),('approved',models.BooleanField(default=False)),('created_at',models.DateTimeField(auto_now_add=True)),('owner',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,to=settings.AUTH_USER_MODEL))])
 ]
