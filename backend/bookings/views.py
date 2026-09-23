from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from chat.services import record_booking
from core.client import get_client_id
from core.exceptions import Conflict
from customers.services import remember_booking_details

from .models import Booking, Service
from .serializers import BookingCreateSerializer, BookingSerializer, ServiceSerializer, SlotQuerySerializer
from .services import create_booking, slot_availability, slot_has_passed


class ServiceListView(APIView):
    """GET /api/services/ - what can be booked, with rough prices."""

    def get(self, request):
        services = Service.objects.filter(is_active=True)
        return Response({"results": ServiceSerializer(services, many=True).data})


class SlotAvailabilityView(APIView):
    """GET /api/booking/slots/?date=YYYY-MM-DD"""

    def get(self, request):
        serializer = SlotQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        day = serializer.validated_data["date"]
        return Response({"date": day, "slots": slot_availability(day)})


class BookingCreateView(APIView):
    """POST /api/booking/ - book a mechanic. A free mechanic is assigned automatically."""

    throttle_scope = "booking"

    def post(self, request):
        client_id = get_client_id(request)
        serializer = BookingCreateSerializer(data=request.data, context={"client_id": client_id})
        serializer.is_valid(raise_exception=True)

        data = dict(serializer.validated_data)
        save_details = data.pop("save_details", False)
        booking = create_booking(**data)
        if booking.conversation:
            record_booking(booking.conversation, booking)
        if save_details:
            remember_booking_details(client_id, booking)

        # the person who just booked can see their own full phone number
        data = BookingSerializer(booking, context={"mask_phone": False}).data
        return Response(data, status=status.HTTP_201_CREATED)


class BookingDetailView(APIView):
    """GET /api/booking/{id}/"""

    def get(self, request, pk):
        booking = get_object_or_404(Booking.objects.select_related("service", "mechanic"), pk=pk)
        return Response(BookingSerializer(booking).data)


class BookingCancelView(APIView):
    """POST /api/booking/{id}/cancel/"""

    throttle_scope = "booking"

    def post(self, request, pk):
        with transaction.atomic():
            booking = get_object_or_404(Booking.objects.select_related("service", "mechanic"), pk=pk)
            if booking.status != Booking.Status.CONFIRMED:
                raise Conflict(f"This booking is already {booking.get_status_display().lower()}.")
            if slot_has_passed(booking.scheduled_date, booking.time_slot):
                raise Conflict("This booking can't be cancelled online any more, please call the garage.")
            booking.status = Booking.Status.CANCELLED
            booking.save(update_fields=["status", "updated_at"])
        return Response(BookingSerializer(booking).data)
