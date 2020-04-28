from django.contrib import admin

from .models import CoverageMeasurement, VegetationMask


class CoverageMeasurementAdmin(admin.ModelAdmin):
    list_display = [
        'date_from',
        'date_to',
        'scope',
        'area',
        'perc_area',
    ]


admin.site.register(VegetationMask)
admin.site.register(CoverageMeasurement, CoverageMeasurementAdmin)
