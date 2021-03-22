from django.contrib.gis import admin
from django.db.models import JSONField
from jsoneditor.forms import JSONEditor
from leaflet.admin import LeafletGeoAdmin

from .models import Place, Station


class PlaceAdmin(LeafletGeoAdmin):
    list_display = ('name', 'parent', 'created_at', 'updated_at')


class StationAdmin(LeafletGeoAdmin):
    list_display = ('code', 'name', 'place', 'lat', 'lon', 'created_at',
                    'updated_at')
    formfield_overrides = {
        JSONField: {
            'widget': JSONEditor
        },
    }


admin.site.register(Place, PlaceAdmin)
admin.site.register(Station, StationAdmin)
