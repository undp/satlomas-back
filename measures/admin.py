from django.contrib import admin

from .models import Device, Place, Station

admin.site.register(Device)
admin.site.register(Place)
admin.site.register(Station)
