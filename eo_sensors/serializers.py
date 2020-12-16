from rest_framework import serializers

from .models import CoverageMeasurement, Raster


class RasterSerializer(serializers.ModelSerializer):
    tiles_url = serializers.ReadOnlyField()

    class Meta:
        model = Raster
        fields = '__all__'
        ref_name = 'LomasChangesRaster'


class CoverageMeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoverageMeasurement
        fields = '__all__'
        ref_name = 'LomasChangesCoverageMeasurement'


class SFTPConnectionSerializer(serializers.Serializer):
    hostname = serializers.CharField()
    port = serializers.IntegerField()
    username = serializers.CharField(required=False)
    password = serializers.CharField(required=False)


class ImportSFTPListSerializer(SFTPConnectionSerializer):
    path = serializers.CharField()


class ImportSFTPSerializer(SFTPConnectionSerializer):
    files = serializers.ListField(child=serializers.CharField())