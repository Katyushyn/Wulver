from django.urls import path

from . import views

app_name = "ai_assistant"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("chat/", views.chat_view, name="chat"),
]
