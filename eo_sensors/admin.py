from django.contrib import admin
from leaflet.admin import LeafletGeoAdmin

from .models import CoverageMeasurement, Raster


class RasterAdmin(admin.ModelAdmin):
    list_display = ("source", "slug", "date", "name", "tiles_url", "file")
    date_hierarchy = "date"
    list_filter = (
        "source",
        "slug",
        "date",
        "name",
    )
    ordering = ("-date", "source", "slug")


class CoverageMeasurementAdmin(admin.ModelAdmin):
    list_display = [
        'date',
        'scope',
        'area_km2',
        'perc_area_100',
    ]
    date_hierarchy = 'created_at'
    ordering = ('-created_at', )


admin.site.register(Raster, RasterAdmin)
admin.site.register(CoverageMeasurement, CoverageMeasurementAdmin)
