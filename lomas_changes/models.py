from django.db import models


class Period(models.Model):
    date_from = models.DateField()
    date_to = models.DateField()

    def __str__(self):
        return '{} - {}'.format(self.date_from, self.date_to)
