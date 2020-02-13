from django.contrib.gis import admin
from leaflet.admin import LeafletGeoAdmin

from .models import Place, Station

admin.site.register(Place, LeafletGeoAdmin)
admin.site.register(Station, LeafletGeoAdmin)
