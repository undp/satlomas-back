from django.contrib.gis import admin
from django.contrib.gis.db.models import PointField
from django.contrib.postgres.fields import HStoreField
from django.db.models import JSONField
from django_admin_hstore_widget.forms import HStoreFormWidget
from jsoneditor.forms import JSONEditor

from .models import Site, Station
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
        HStoreField: {"widget": HStoreFormWidget},
    }
    # attributes = HStoreFormField()


admin.site.register(Station, StationAdmin)
admin.site.register(Site, SiteAdmin)
