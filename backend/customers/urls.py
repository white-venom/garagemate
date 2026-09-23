from django.urls import path

from . import views

urlpatterns = [
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("profile/cars/", views.CarListView.as_view(), name="car-list"),
    path("profile/cars/<int:pk>/", views.CarDetailView.as_view(), name="car-detail"),
]
