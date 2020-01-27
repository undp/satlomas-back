from django.shortcuts import render
from rest_framework import viewsets

from .models import Place, Station
from .serializers import PlaceSerializer, StationSerializer


class PlaceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Place.objects.all().order_by('-name')
    serializer_class = PlaceSerializer


class StationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Station.objects.all().order_by('-name')
    serializer_class = StationSerializer
