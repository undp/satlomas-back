from django.db.models.signals import post_save
from django.dispatch import receiver
from jobs.utils import enqueue_job

from scopes.models import Scope


@receiver(post_save, sender=Scope)
def update_measurements(sender, instance, created, **kwargs):
    enqueue_job("eo_sensors.tasks.scopes.update_measurements", scope_id=instance.pk)
