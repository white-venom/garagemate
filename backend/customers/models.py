from django.db import models

MAX_CARS = 5


class Customer(models.Model):
    """
    Optional profile for a browser (client id). Lets the bot greet people by name,
    ask "is this about your Swift?" and prefill the booking form.
    """

    client_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=16, blank=True)
    email = models.EmailField(blank=True)
    city = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name or self.client_id

    @property
    def first_name(self):
        return self.name.split()[0] if self.name else ""


class Car(models.Model):
    class Fuel(models.TextChoices):
        PETROL = "petrol", "Petrol"
        DIESEL = "diesel", "Diesel"
        CNG = "cng", "CNG"
        ELECTRIC = "electric", "Electric"
        HYBRID = "hybrid", "Hybrid"
        LPG = "lpg", "LPG"

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="cars")
    make = models.CharField(max_length=40)
    model = models.CharField(max_length=60)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    fuel_type = models.CharField(max_length=12, choices=Fuel.choices, blank=True)
    odometer_km = models.PositiveIntegerField(null=True, blank=True)
    registration_number = models.CharField(max_length=15, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "created_at"]

    def __str__(self):
        return self.label

    @property
    def label(self):
        return " ".join(str(part) for part in (self.year, self.make, self.model) if part)

    @property
    def short_name(self):
        return self.model or self.make
