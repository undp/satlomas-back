from django.db import models
from datetime import datetime


class Device(models.Model):
    code = models.CharField(max_length=32)
    location = models.CharField(max_length=64)

    def __str__(self):
        return '{code} - {location}'.format(code=self.code,
                                            location=self.location)     

class Measure(models.Model):
    datetime = models.DateTimeField(default=datetime.now, blank=True, primary_key=True)
    temperature = models.FloatField()
    humidity = models.FloatField()
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='measures')

    class Meta:
        unique_together = (('datetime', 'device'),)

    def __str__(self):
        return '{datetime} - {measure} - {device}'.format(
            datetime=self.datetime,
            measure=self.measure,
            device=self.device
        )