from django.contrib import admin
from leaflet.admin import LeafletGeoAdmin

from .models import Scope


class ScopeAdmin(LeafletGeoAdmin):
    list_display = ['scope_type', 'name', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'


admin.site.register(Scope, ScopeAdmin)
