from django.contrib.gis import admin
from django.contrib.gis.db.models import PointField
from django.db.models import JSONField
from jsoneditor.forms import JSONEditor

from .models import Station, Site
from .widgets import LatLongWidget


class StationAdmin(admin.ModelAdmin):
    list_display = ("code", "created_at", "updated_at")
    formfield_overrides = {
        JSONField: {"widget": JSONEditor},
    }


class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "geom", "created_at", "updated_at")
    formfield_overrides = {
        PointField: {"widget": LatLongWidget},
        JSONField: {"widget": JSONEditor},
    }


admin.site.register(Station, StationAdmin)
admin.site.register(Site, SiteAdmin)
