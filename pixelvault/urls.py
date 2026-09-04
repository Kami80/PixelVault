from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from workspace import views as workspace_views
import pet.views as pet_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("setup/", workspace_views.first_run_setup, name="first_run_setup"),
    path("login/", workspace_views.login_router, name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("workspace.urls")),
    path("pet/", include("pet.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
