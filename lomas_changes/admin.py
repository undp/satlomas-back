from django.contrib import admin

from .models import CoverageMeasurement, Period, Raster


class CoverageMeasurementAdmin(admin.ModelAdmin):
    list_display = [
        'date_from',
        'date_to',
        'scope',
        'change_area',
        'perc_change_area',
    ]


class PeriodAdmin(admin.ModelAdmin):
    readonly_fields = (
        'date_from',
        'date_to',
    )
    date_hierarchy = 'date_from'


admin.site.register(CoverageMeasurement, CoverageMeasurementAdmin)
admin.site.register(Raster)
admin.site.register(Period, PeriodAdmin)

