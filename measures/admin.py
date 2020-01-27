from django.contrib import admin

from .models import Place, Station


class StationAdmin(admin.ModelAdmin):
    exclude = ('geom', )


admin.site.register(Place)
admin.site.register(Station, StationAdmin)
