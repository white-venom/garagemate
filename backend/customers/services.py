from django.db import transaction

from core.text import mentions, normalize

from .models import MAX_CARS, Car, Customer


def get_customer(client_id):
    return Customer.objects.filter(client_id=client_id).prefetch_related("cars").first()


def make_primary(car):
    with transaction.atomic():
        Car.objects.filter(customer_id=car.customer_id).exclude(pk=car.pk).update(is_primary=False)
        if not car.is_primary:
            car.is_primary = True
            car.save(update_fields=["is_primary"])


def add_car(customer, **fields):
    first_car = not customer.cars.exists()
    car = Car.objects.create(customer=customer, **{**fields, "is_primary": fields.get("is_primary") or first_car})
    if car.is_primary:
        make_primary(car)
    return car


def delete_car(car):
    customer, was_primary = car.customer, car.is_primary
    car.delete()
    if was_primary:
        replacement = customer.cars.order_by("created_at").first()
        if replacement:
            make_primary(replacement)


def find_mentioned_car(cars, text):
    """
    The saved car the message talks about, if it's clear: "my swift" matches a
    saved Swift, "my maruti" works too as long as there's only one Maruti.
    """
    normalized = normalize(text)
    # prefix match so "my swift's ac" (-> "swifts") still counts
    by_model = [car for car in cars if car.model and mentions(normalized, f"{car.model}*")]
    if len(by_model) == 1:
        return by_model[0]
    by_make = [car for car in cars if mentions(normalized, f"{car.make.split()[0]}*")]
    if len(by_make) == 1:
        return by_make[0]
    return None


def remember_booking_details(client_id, booking):
    """Save the name / phone / car from a booking to the profile ("save my details" was ticked)."""
    customer, _ = Customer.objects.get_or_create(client_id=client_id)
    customer.name = booking.customer_name
    customer.phone = booking.phone
    if booking.email:
        customer.email = booking.email
    customer.save()

    cars = list(customer.cars.all())
    same = next(
        (
            car
            for car in cars
            if (booking.registration_number and car.registration_number == booking.registration_number)
            or (normalize(car.make) == normalize(booking.vehicle_make) and normalize(car.model) == normalize(booking.vehicle_model))
        ),
        None,
    )
    if same:
        same.year = booking.vehicle_year or same.year
        same.registration_number = booking.registration_number or same.registration_number
        same.save(update_fields=["year", "registration_number"])
    elif len(cars) < MAX_CARS:
        add_car(
            customer,
            make=booking.vehicle_make,
            model=booking.vehicle_model,
            year=booking.vehicle_year,
            registration_number=booking.registration_number,
        )
    return customer
