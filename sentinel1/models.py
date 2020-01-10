from django.db import models


class Period(models.Model):
    init_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return '{init_date}_{end_date}'.format(init_date=self.init_date,
                                                end_date=self.end_date)


class Product(models.Model):
    code = models.CharField(max_length=128)
    period = models.ForeignKey(Period, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=128)
    datetime = models.DateTimeField(null=True)
    concatenated = models.BooleanField(default=False)

    def __str__(self):
        return self.name
