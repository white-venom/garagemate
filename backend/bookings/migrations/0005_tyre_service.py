from django.db import migrations


def add_service(apps, schema_editor):
    Service = apps.get_model("bookings", "Service")
    Service.objects.update_or_create(
        code="tyre-service",
        defaults={
            "name": "Tyre & Puncture Repair",
            "description": "Puncture repair, valve replacement, tyre pressure and condition check. New tyres are quoted "
            "separately after inspection.",
            "price_min": 150,
            "price_max": 1500,
            "duration_minutes": 45,
        },
    )


def remove_service(apps, schema_editor):
    apps.get_model("bookings", "Service").objects.filter(code="tyre-service").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0004_mileage_checkup_service"),
    ]

    operations = [
        migrations.RunPython(add_service, remove_service),
    ]
