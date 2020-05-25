from rest_framework import serializers

from .models import CoverageMeasurement, Period, Raster


class PeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Period
        exclude = ('id', )
        ref_name = 'VILomasChangesPeriod'


class RasterSerializer(serializers.ModelSerializer):
    tiles_url = serializers.ReadOnlyField()
    period = PeriodSerializer()

    class Meta:
        model = Raster
        fields = '__all__'
        ref_name = 'VILomasChangesRaster'


class CoverageMeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoverageMeasurement
        fields = '__all__'
        ref_name = 'LomasChangesCoverageMeasurement'
