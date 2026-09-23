from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    # the cache table isn't a model, so migrate wouldn't make it on its own
    call_command("createcachetable", verbosity=0)


class Migration(migrations.Migration):
    dependencies = [
        ("apilogs", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_cache_table, migrations.RunPython.noop),
    ]
