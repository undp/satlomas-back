from django.contrib.gis import admin

from .models import Scope

admin.site.register(Scope, admin.GeoModelAdmin)
