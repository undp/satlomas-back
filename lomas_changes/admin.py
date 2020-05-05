from django.contrib import admin

from .models import CoverageMeasurement


class CoverageMeasurementAdmin(admin.ModelAdmin):
    list_display = [
        'date_from',
        'date_to',
        'scope',
        'change_area',
        'perc_change_area',
    ]


admin.site.register(CoverageMeasurement, CoverageMeasurementAdmin)
