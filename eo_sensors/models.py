from django.conf import settings
from django.contrib.gis.db import models
from django.db.models import JSONField
from django.utils.translation import gettext_lazy as _


class Sources(models.TextChoices):
    SEN2 = "S2", _("Sentinel-2")
    PS1 = "P1", _("PeruSat-1")
    MODIS_VI = "MV", _("MODIS VI")


def raster_path(instance, filename):
    return "rasters/{path}/{filename}".format(path=instance.path(), filename=filename)


class Raster(models.Model):
    slug = models.SlugField()
    date = models.DateField(null=True)
    source = models.CharField(max_length=2, choices=Sources.choices, blank=True)
    file = models.FileField(upload_to=raster_path, blank=True, null=True)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    extra_fields = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("slug", "date"),)

    def __str__(self):
        return f"[{self.source}] {self.date} {self.name}"

    def tiles_url(self):
        return f"{settings.TILE_SERVER_URL}{self.path()}" + "{z}/{x}/{y}.png"

    def path(self):
        date_str = self.date.strftime("%Y%m%d")
        return f"{self.slug}/{date_str}/"


class CoverageMask(models.Model):
    date = models.DateField(null=True)
    source = models.CharField(max_length=2, choices=Sources.choices, blank=True)
    kind = models.CharField(max_length=2, blank=True, null=True)
    raster = models.ForeignKey(Raster, on_delete=models.CASCADE)
    geom = models.MultiPolygonField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["date", "source", "kind"]

    def __str__(self):
        return "{date} :: {source}:{kind}".format(
            source=self.source,
            date=self.date,
            kind=self.kind,
        )


class CoverageRaster(models.Model):
    raster = models.ForeignKey(Raster, on_delete=models.CASCADE)
    cov_rast = models.RasterField(srid=32718)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CoverageMeasurement(models.Model):
    date = models.DateField()
    scope = models.ForeignKey(
        "scopes.Scope",
        related_name="%(app_label)s_%(class)s_related",
        on_delete=models.SET_NULL,
        null=True,
    )
    source = models.CharField(max_length=2, choices=Sources.choices, blank=True)
    kind = models.CharField(max_length=2)
    area = models.FloatField()
    perc_area = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["date", "scope", "source", "kind"]

    def __str__(self):
        return (
            "{date} :: {scope} :: {source}:{kind} :: {area}km2 ({perc_area}%)".format(
                source=self.source,
                kind=self.kind,
                date=self.date,
                scope=self.scope and self.scope.name,
                area=self.area_km2(),
                perc_area=self.perc_area_100(),
            )
        )

    def area_km2(self):
        return round(self.area / 1000000, 2)

    def perc_area_100(self):
        return round(self.perc_area * 100, 2)
