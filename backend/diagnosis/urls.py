from django.urls import path

from . import views

urlpatterns = [
    path("diagnosis/", views.DiagnosisView.as_view(), name="diagnosis"),
    path("diagnosis/<int:pk>/", views.DiagnosisDetailView.as_view(), name="diagnosis-detail"),
]
