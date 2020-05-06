from rest_framework import serializers

from .models import Period, Raster


class PeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Period
        exclude = ('id', )


class RasterSerializer(serializers.ModelSerializer):
    tiles_url = serializers.ReadOnlyField()
    extent_geom = serializers.ReadOnlyField()
    period = PeriodSerializer()

    class Meta:
        model = Raster
        fields = '__all__'