from django.contrib.gis.db import models

# Create your models here.
class VegetationMask(models.Model):
    period = models.DateField()
    mask = models.MultiPolygonField()