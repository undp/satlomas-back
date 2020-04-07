from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Measure, Place, Station
from .serializers import (MeasureSummarySerializer, PlaceSerializer,
                          StationSerializer)


class PlaceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Place.objects.all().order_by('-name')
    serializer_class = PlaceSerializer


class StationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Station.objects.all().order_by('-name')
    serializer_class = StationSerializer


class MeasureSummaryView(APIView):
    def get(self, request, *args, **kwargs):
        serializer = MeasureSummarySerializer(data=request.query_params)
        # print("Query params", request.query_params)
        if not serializer.is_valid():
            # print(serializer.errors)
            return Response(data=serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)
        summary = Measure.objects.summary(**serializer.data)
        return Response(summary)
