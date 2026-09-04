from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django import forms


class FirstRunSetupForm(UserCreationForm):
    display_name = forms.CharField(max_length=60, initial="Local Builder")
    workspace_name = forms.CharField(max_length=60, initial="PixelVault")
    seed_examples = forms.BooleanField(required=False, initial=True, label="Create starter examples")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "display_name", "workspace_name", "password1", "password2", "seed_examples")
