from django.urls import path

from . import views

urlpatterns = [
    path("services/", views.ServiceListView.as_view(), name="service-list"),
    path("booking/", views.BookingCreateView.as_view(), name="booking-create"),
    path("booking/slots/", views.SlotAvailabilityView.as_view(), name="booking-slots"),
    path("booking/<uuid:pk>/", views.BookingDetailView.as_view(), name="booking-detail"),
    path("booking/<uuid:pk>/cancel/", views.BookingCancelView.as_view(), name="booking-cancel"),
]
