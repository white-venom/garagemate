from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apilogs.models import RequestLog


class Command(BaseCommand):
    help = "Delete old API request logs (runs daily from cron)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options["days"])
        deleted, _ = RequestLog.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f"Removed {deleted} old log(s)"))
