from django.urls import path

from . import views

urlpatterns = [
    path("logs/", views.RequestLogView.as_view(), name="request-logs"),
    path("ai/check/", views.GeminiCheckView.as_view(), name="ai-check"),
]
