from django.db import migrations

# prices are rough ranges in INR for a typical hatchback / sedan
SERVICES = [
    ("periodic-service", "Periodic Service", "Engine oil and filter change, air filter check, fluid top-ups and a 40 point inspection.", 2500, 6000, 180),
    ("general-inspection", "Complete Inspection", "Full check of the car with an OBD scan. Good when you're not sure what's wrong.", 499, 999, 60),
    ("brake-service", "Brake Service", "Inspect pads, discs, calipers and brake fluid. Replace pads or resurface discs if needed.", 1200, 6500, 90),
    ("battery-electrical", "Battery & Electrical Repair", "Battery test, charging system check, starter motor, fuses and wiring faults.", 500, 7500, 60),
    ("engine-diagnostics", "Engine Diagnostics & Tune-up", "OBD scan, spark plugs, ignition coils, injector and throttle body cleaning, sensor checks.", 1000, 8000, 120),
    ("cooling-system", "Cooling System Repair", "Pressure test for leaks, radiator, fan, thermostat and water pump checks, coolant flush.", 1200, 9000, 120),
    ("clutch-transmission", "Clutch & Gearbox Repair", "Clutch plate, pressure plate, release bearing and hydraulics, gearbox oil / ATF service.", 2500, 25000, 240),
    ("suspension-steering", "Suspension & Steering Repair", "Shock absorbers, bushes, links, ball joints, tie rods and power steering.", 1500, 15000, 150),
    ("wheel-alignment", "Wheel Alignment & Balancing", "Computerised alignment, wheel balancing, tyre rotation and puncture repair.", 600, 2000, 60),
    ("ac-service", "AC Service & Gas Refill", "AC performance check, leak test, gas top-up, cabin filter and vent cleaning.", 1500, 5500, 90),
    ("leak-inspection", "Leak Inspection & Repair", "Trace oil, coolant, fuel or other fluid leaks and replace the gasket, seal or hose.", 800, 7000, 90),
]

MECHANICS = [
    ("Rakesh Kumar", "+919000000101", "Engine & transmission", 14),
    ("Imran Shaikh", "+919000000102", "Brakes & suspension", 9),
    ("Suresh Pillai", "+919000000103", "Electrical & AC", 11),
    ("Gurpreet Singh", "+919000000104", "General service", 6),
]


def seed(apps, schema_editor):
    Service = apps.get_model("bookings", "Service")
    Mechanic = apps.get_model("bookings", "Mechanic")

    for code, name, description, price_min, price_max, minutes in SERVICES:
        Service.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": description,
                "price_min": price_min,
                "price_max": price_max,
                "duration_minutes": minutes,
            },
        )

    for name, phone, speciality, years in MECHANICS:
        Mechanic.objects.get_or_create(
            name=name, defaults={"phone": phone, "speciality": speciality, "experience_years": years}
        )


def unseed(apps, schema_editor):
    apps.get_model("bookings", "Service").objects.filter(code__in=[s[0] for s in SERVICES]).delete()
    apps.get_model("bookings", "Mechanic").objects.filter(name__in=[m[0] for m in MECHANICS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
