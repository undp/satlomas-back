from rest_framework import serializers

from .models import Place, Station


class PlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Place


class StationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Station
