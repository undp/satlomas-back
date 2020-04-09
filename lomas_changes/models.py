from django.db import models


class Period(models.Model):
    init_date = models.DateField()
    end_date = models.DateField()
    s1_finished = models.BooleanField(default=False)
    s2_finished = models.BooleanField(default=False)

    def __str__(self):
        return '{init_date}_{end_date}'.format(init_date=self.init_date,
                                               end_date=self.end_date)


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
