from rest_framework import serializers

from .models import CoverageMeasurement, Mask, Period, Raster


class PeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Period
        exclude = ('id', )
        ref_name = 'LomasChangesPeriod'


class RasterSerializer(serializers.ModelSerializer):
    tiles_url = serializers.ReadOnlyField()

    period = PeriodSerializer()

    class Meta:
        model = Raster
        fields = '__all__'
        ref_name = 'LomasChangesRaster'


class MaskSerializer(serializers.ModelSerializer):
    period = PeriodSerializer()

    class Meta:
        model = Mask
        fields = '__all__'
        ref_name = 'LomasChangesMask'


class CoverageMeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoverageMeasurement
        fields = '__all__'
        ref_name = 'LomasChangesCoverageMeasurement'
