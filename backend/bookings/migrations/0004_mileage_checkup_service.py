from django.db import migrations


def add_service(apps, schema_editor):
    Service = apps.get_model("bookings", "Service")
    Service.objects.update_or_create(
        code="mileage-checkup",
        defaults={
            "name": "Mileage Check-up & Tune-up",
            "description": "Tyre pressure and alignment, air filter, spark plugs, injector cleaning, OBD scan and a "
            "road test to find where the fuel is going.",
            "price_min": 999,
            "price_max": 4500,
            "duration_minutes": 120,
        },
    )


def remove_service(apps, schema_editor):
    apps.get_model("bookings", "Service").objects.filter(code="mileage-checkup").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0003_seed_services_and_mechanics"),
    ]

    operations = [
        migrations.RunPython(add_service, remove_service),
    ]
