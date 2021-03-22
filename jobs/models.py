import django_rq
from django.conf import settings
from django.db.models import JSONField
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from jobs import signals, states


class Job(models.Model):
    JOB_STATE_CHOICES = sorted(zip(states.ALL_STATES, states.ALL_STATES))

    name = models.CharField(_("name"), max_length=255)
    args = JSONField(_("arguments"), default=list, blank=True)
    kwargs = JSONField(_("keyword arguments"), default=dict, blank=True)
    queue = models.CharField(_("queue"), max_length=64, blank=True, null=True)
    state = models.CharField(
        _("state"), max_length=50, default=states.PENDING, choices=JOB_STATE_CHOICES
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    finished_at = models.DateTimeField(_("finished at"), null=True, blank=True)
    metadata = JSONField(_("metadata"), default=dict, blank=True)
    error = models.TextField(_("error"), blank=True, null=True)
    estimated_duration = models.PositiveIntegerField(
        _("estimated duration"), blank=True, null=True
    )
    internal_metadata = JSONField(_("internal metadata"), default=dict, blank=True)

    def __str__(self):
        return f"{self.name}({self.args}, {self.kwargs})"

    @property
    def status(self):
        return self.metadata.get("status")

    @property
    def duration(self):
        """
        Returns the duration of a stopped job, in seconds

        If the job is still running or pending, returns None.

        """
        if self.has_stopped():
            return abs(self.finished_at - self.created_at).seconds

    @property
    def age(self):
        """
        Returns job age in seconds

        """
        return (timezone.now() - self.created_at).seconds

    @property
    def can_be_cancelled(self):
        """
        Returns True if the job can be cancelled

        """
        # Jobs cannot be cancelled for now
        return False

    def start(self, sync=False):
        if self.state == states.PENDING:
            if sync:
                method = self._get_function_from_string(self.name)
                method(self.pk, sync=True)
            else:
                queue = django_rq.get_queue(self.queue or "default")
                queue.enqueue(self.name, self.pk)
            self.state = states.STARTED
            self.save(update_fields=["state", "updated_at"])
            signals.job_started.send(sender=self.__class__, job=self)
            return True
        return False

    def retry(self):
        if not self.state == states.FAILED:
            raise RuntimeError("Cannot retry a job that has not failed")
        self.state = states.PENDING
        self.traceback = None
        self.save(update_fields=["state", "traceback", "updated_at"])
        self.start()

    def cancel(self):
        if self.can_be_cancelled:
            if self.state in [states.CANCELED, states.FINISHED, states.FAILED]:
                raise RuntimeError("Cannot cancel an already completed job")
        else:
            raise RuntimeError("This job can not be canceled")

    def is_pending(self):
        return self.state == states.PENDING

    def is_running(self):
        return self.state == states.STARTED

    def has_stopped(self):
        return self.state in [states.FINISHED, states.FAILED, states.CANCELED]

    def has_finished(self):
        return self.state == states.FINISHED

    def has_failed(self):
        return self.state == states.FAILED

    def has_been_canceled(self):
        return self.state == states.CANCELED

    def update_status(self, status):
        if self.metadata is None:
            self.metadata = {}
        self.metadata["status"] = str(status)
        self.save(update_fields=["metadata", "updated_at"])

    def mark_as_finished(self, finished_at=None):
        self._mark_as(states.FINISHED, finished_at=finished_at)
        signals.job_finished.send(sender=self.__class__, job=self)

    def mark_as_canceled(self, finished_at=None):
        self._mark_as(states.CANCELED, finished_at=finished_at)
        signals.job_canceled.send(sender=self.__class__, job=self)

    def mark_as_failed(self, reason=None, finished_at=None):
        self._mark_as(states.FAILED, finished_at=finished_at)
        self.error = reason
        self.save(update_fields=["error", "updated_at"])
        signals.job_failed.send(sender=self.__class__, job=self)

    def _mark_as(self, state, finished_at=None):
        """Mark a Job as stopped with a state (FINISHED, FAILED, CANCELED)"""
        self.state = state
        self.finished_at = finished_at or timezone.now()
        self.save(update_fields=["state", "finished_at", "updated_at"])

    @staticmethod
    def _get_function_from_string(s):
        import importlib

        # First import module
        parts = s.split(".")
        module_s = ".".join(parts[:-1])
        mod = importlib.import_module(module_s)

        # Return method by fetching attribute from module
        method_s = parts[-1]
        return getattr(mod, method_s)


class JobLogEntry(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    logged_at = models.DateTimeField()
    log = JSONField()

    class Meta:
        verbose_name = _("job log entry")
        verbose_name_plural = _("job log entries")
