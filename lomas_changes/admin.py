from django.contrib import admin
from leaflet.admin import LeafletGeoAdmin

from .models import CoverageMeasurement, Mask, Period, Raster


class RasterAdmin(admin.ModelAdmin):
    list_display = ('slug', 'period', 'name', 'tiles_url')
    date_hierarchy = 'period__date_to'
    ordering = ('-period__date_from', '-period__date_to')


class PeriodAdmin(admin.ModelAdmin):
    readonly_fields = (
        'date_from',
        'date_to',
    )
    date_hierarchy = 'date_to'
    ordering = ('-date_from', '-date_to')


class MaskAdmin(LeafletGeoAdmin):
    list_display = ['period', 'mask_type', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    ordering = ('-created_at', )


class CoverageMeasurementAdmin(admin.ModelAdmin):
    list_display = [
        'date_from',
        'date_to',
        'scope',
        'area_km2',
        'perc_area_100',
    ]
    date_hierarchy = 'created_at'
    ordering = ('-created_at', )


admin.site.register(Raster, RasterAdmin)
admin.site.register(Period, PeriodAdmin)
admin.site.register(Mask, MaskAdmin)
admin.site.register(CoverageMeasurement, CoverageMeasurementAdmin)

