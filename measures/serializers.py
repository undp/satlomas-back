from rest_framework import serializers

from .models import Place, Station


class PlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Place
        fields = '__all__'


class StationSerializer(serializers.ModelSerializer):
    place_name = serializers.ReadOnlyField()

    class Meta:
        model = Station
        fields = '__all__'
