from django.contrib import admin
from leaflet.admin import LeafletGeoAdmin

from .models import CoverageMeasurement, CoverageRaster, Raster


class RasterAdmin(admin.ModelAdmin):
    list_display = ('slug', 'date', 'name', 'tiles_url')
    date_hierarchy = 'date'
    ordering = ('-date', )


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
admin.site.register(CoverageRaster)
admin.site.register(CoverageMeasurement, CoverageMeasurementAdmin)
