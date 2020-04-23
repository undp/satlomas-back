from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView
from rest_framework_csv import renderers as r

from .models import Measurement, Place, Station
from .serializers import (MeasurementSummarySerializer, PlaceSerializer,
                          StationSerializer)


class PlaceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Place.objects.all().order_by('-name')
    serializer_class = PlaceSerializer


class StationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Station.objects.all().order_by('-name')
    serializer_class = StationSerializer


class MeasurementSummaryView(APIView):
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + [r.CSVRenderer]

    def get(self, request):
        serializer = MeasurementSummarySerializer(data=request.query_params)
        if not serializer.is_valid():
            print(serializer.errors)
            return Response(data=serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)
        summary = list(Measurement.objects.summary(**serializer.data))
        return Response(summary)
