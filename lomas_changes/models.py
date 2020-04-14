from django.db import models


class Period(models.Model):
    date_from = models.DateField()
    date_to = models.DateField()

    def __str__(self):
        return '{} - {}'.format(self.date_from, self.date_to)


class Product(models.Model):
    SENTINEL1 = 'S1'
    SENTINEL2 = 'S2'

    SENSOR_CHOICES = [
        (SENTINEL1, 'Sentinel1'),
        (SENTINEL2, 'Sentinel2'),
    ]
    code = models.CharField(max_length=128)
    sensor_type = models.CharField(
        max_length=2,
        choices=SENSOR_CHOICES,
    )
    period = models.ForeignKey(Period,
                               on_delete=models.CASCADE,
                               related_name="products")
    name = models.CharField(max_length=128)
    datetime = models.DateTimeField(null=True)
    concatenated = models.BooleanField(default=False)

    def __str__(self):
        return self.name
