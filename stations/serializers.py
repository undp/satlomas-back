from rest_framework import serializers

from .models import Station, Site, Measurement


class StationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Station
        fields = "__all__"


class SiteSerializer(serializers.ModelSerializer):
    station_code = serializers.CharField(source="station.code")

    class Meta:
        model = Site
        fields = "__all__"
        read_only_fields = (
            "station",
            "station_code",
        )


class MeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Measurement
        fields = "__all__"


class MeasurementSummarySerializer(serializers.Serializer):
    site = serializers.IntegerField()
    parameter = serializers.CharField()
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    grouping_interval = serializers.ChoiceField(
        choices=["hour", "day", "week", "month", "year"], default="day"
    )
    aggregation_func = serializers.ChoiceField(
        choices=["avg", "sum", "count", "min", "max"], default="avg"
    )
