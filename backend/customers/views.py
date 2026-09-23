from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.client import get_client_id

from .models import Car, Customer
from .serializers import CarSerializer, ProfileSerializer
from .services import add_car, delete_car, get_customer, make_primary

EMPTY_PROFILE = {"name": "", "phone": "", "email": "", "city": "", "cars": []}


class ProfileView(APIView):
    """GET / PUT /api/profile/ - the visitor's name, contact details and saved cars."""

    def get(self, request):
        customer = get_customer(get_client_id(request))
        return Response(ProfileSerializer(customer).data if customer else EMPTY_PROFILE)

    def put(self, request):
        customer, _ = Customer.objects.get_or_create(client_id=get_client_id(request))
        serializer = ProfileSerializer(customer, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProfileSerializer(get_customer(customer.client_id)).data)


class CarListView(APIView):
    """POST /api/profile/cars/ - save a car. The first one becomes the primary car."""

    def post(self, request):
        customer, _ = Customer.objects.get_or_create(client_id=get_client_id(request))
        serializer = CarSerializer(data=request.data, context={"customer": customer})
        serializer.is_valid(raise_exception=True)
        car = add_car(customer, **serializer.validated_data)
        return Response(CarSerializer(car).data, status=status.HTTP_201_CREATED)


class CarDetailView(APIView):
    """PATCH / DELETE /api/profile/cars/{id}/"""

    def get_car(self, request, pk):
        return get_object_or_404(Car, pk=pk, customer__client_id=get_client_id(request))

    def patch(self, request, pk):
        car = self.get_car(request, pk)
        serializer = CarSerializer(car, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        car = serializer.save()
        if serializer.validated_data.get("is_primary"):
            make_primary(car)
        return Response(CarSerializer(car).data)

    def delete(self, request, pk):
        delete_car(self.get_car(request, pk))
        return Response(status=status.HTTP_204_NO_CONTENT)
