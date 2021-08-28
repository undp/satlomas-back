from rest_framework import serializers

from .models import Station, Measurement


class StationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Station
        fields = "__all__"


class MeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Measurement
        fields = "__all__"


class MeasurementSummarySerializer(serializers.Serializer):
    station = serializers.IntegerField()
    parameter = serializers.CharField()
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    grouping_interval = serializers.ChoiceField(
        choices=["hour", "day", "week", "month", "year"], default="day"
    )
    aggregation_func = serializers.ChoiceField(
        choices=["avg", "sum", "count", "min", "max"], default="avg"
    )
