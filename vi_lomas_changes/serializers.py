from rest_framework import serializers

from .models import Raster


class RasterSerializer(serializers.ModelSerializer):
    tiles_url = serializers.ReadOnlyField()
    extent_geom = serializers.ReadOnlyField()

    class Meta:
        model = Raster
        exclude = ('id', )
