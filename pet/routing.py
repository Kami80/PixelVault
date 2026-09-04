from django.urls import path
from .consumers import PetConsumer
websocket_urlpatterns=[path("ws/pet/",PetConsumer.as_asgi())]
