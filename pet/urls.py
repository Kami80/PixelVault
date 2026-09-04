from django.urls import path

from . import views

urlpatterns = [
    path("", views.pet_page, name="pet"),
    path("chat/", views.pet_chat, name="pet_chat"),
    path("chats/new/", views.pet_chat_new, name="pet_chat_new"),
    path("object-action/", views.pet_object_action, name="pet_object_action"),
    path("memory/", views.pet_memory, name="pet_memory"),
]
