from django.db import models


class Period(models.Model):
    date_from = models.DateField()
    date_to = models.DateField()

    def __str__(self):
        return '{} - {}'.format(self.date_from, self.date_to)


class CoverageMeasurement(models.Model):
    date_from = models.DateField()
    date_to = models.DateField()
    scope = models.ForeignKey('scopes.Scope',
                              related_name='lomas_changes_scope',
                              on_delete=models.SET_NULL,
                              null=True)
    change_area = models.FloatField()
    perc_change_area = models.FloatField()

    class Meta:
        unique_together = ['date_from', 'date_to', 'scope']