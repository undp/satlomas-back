import json

from django import forms
from django.contrib import admin
from django.contrib.gis.geos import GEOSGeometry
from leaflet.admin import LeafletGeoAdmin

from .models import Scope


class ScopeForm(forms.ModelForm):
    geom_geojson_file = forms.FileField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['geom'].required = False
        self.fields['geom_geojson_file'].required = False

    def save(self, commit=True):
        instance = super().save(commit=False)
        geom_geojson_file = self.cleaned_data.get('geom_geojson_file', None)
        if geom_geojson_file:
            geojson = json.load(geom_geojson_file)
            feature = geojson['features'][0]
            polygon = GEOSGeometry(json.dumps(feature['geometry']))
            instance.geom = polygon
        if commit:
            instance.save()
        return instance

    class Meta:
        model = Scope
        fields = '__all__'


class ScopeAdmin(LeafletGeoAdmin):
    form = ScopeForm
    list_display = ['scope_type', 'name', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'


admin.site.register(Scope, ScopeAdmin)
