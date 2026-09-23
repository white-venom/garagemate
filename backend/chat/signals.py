from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Attachment


@receiver(post_delete, sender=Attachment)
def delete_attachment_file(sender, instance, **kwargs):
    # rows get deleted with their conversation, don't leave the files behind
    if instance.file:
        instance.file.delete(save=False)
