from django.contrib.gis import admin
from django.db.models import JSONField
from jsoneditor.forms import JSONEditor
from leaflet.admin import LeafletGeoAdmin

from .models import Station


class StationAdmin(LeafletGeoAdmin):
    list_display = ("code", "name", "geom", "created_at", "updated_at")
    formfield_overrides = {
        JSONField: {"widget": JSONEditor},
    }


admin.site.register(Station, StationAdmin)
