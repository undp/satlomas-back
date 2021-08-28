from rest_framework import status, viewsets, permissions
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView
from rest_framework_csv import renderers as r

from .models import Measurement, Station
from .serializers import (
    MeasurementSummarySerializer,
    StationSerializer,
)


class StationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    queryset = Station.objects.all().order_by("-name")
    serializer_class = StationSerializer

    def get_queryset(self):
        queryset = Station.objects.all()
        name = self.request.query_params.get("name", None)
        if name is not None:
            queryset = queryset.filter(name__icontains=name)
        return queryset


class MeasurementSummaryView(APIView):
    permission_classes = [permissions.AllowAny]
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + [r.CSVRenderer]

    def get(self, request):
        serializer = MeasurementSummarySerializer(data=request.query_params)
        if not serializer.is_valid():
            print(serializer.errors)
            return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        summary = list(Measurement.objects.summary(**serializer.data))
        return Response(summary)
