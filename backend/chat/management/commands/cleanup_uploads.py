from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from chat.models import Attachment


class Command(BaseCommand):
    help = "Delete uploads that were never sent in a chat message (runs daily from cron)."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24, help="Only delete uploads older than this")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=options["hours"])
        orphans = Attachment.objects.filter(message__isnull=True, created_at__lt=cutoff)
        count = 0
        # delete one by one so the post_delete signal removes the files too
        for attachment in orphans.iterator():
            attachment.delete()
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Removed {count} unused upload(s)"))
