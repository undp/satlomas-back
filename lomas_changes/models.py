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
                              related_name="%(app_label)s_%(class)s_related",
                              on_delete=models.SET_NULL,
                              null=True)
    change_area = models.FloatField()
    perc_change_area = models.FloatField()

    class Meta:
        unique_together = ['date_from', 'date_to', 'scope']

    def __str__(self):
        return '{dfrom}-{dto} :: {scope} :: {value} ({perc}%)'.format(
            dfrom=self.date_from,
            dto=self.date_to,
            scope=self.scope.name,
            value=self.change_area,
            perc=self.perc_change_area)
