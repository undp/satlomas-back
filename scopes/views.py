from datetime import datetime, timedelta

import pandas as pd
import shapely.wkt
from django.contrib.auth.models import User
from django.db import connection
from django.shortcuts import render
from rest_framework import authentication, permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ScopeSerializer
from .models import Scope

from vi_lomas_changes.models import Mask


def intersection_area_sql(scope_geom, date):
    mask = Mask.objects.filter(period=date, mask_type='ndvi').first()
    query = """SELECT ST_Area(a.int) AS area
               FROM (
                   SELECT ST_Intersection(
                       ST_Transform(ST_GeomFromText('{wkt_scope}', 4326), {srid}),
                       ST_Transform(ST_GeomFromText('{wkt_mask}', 4326), {srid})) AS int) a;
            """.format(wkt_scope=scope_geom.wkt, wkt_mask=mask.geom.wkt)
    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()[0][0]


class TimeSeries(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data
        scope_id = data['scope_id'] if 'scope_id' in data else None
        if scope_id is None:
            mp_geometry = data['geometry'] if 'geometry' in data else None
            if mp_geometry is None:
                Exception("No data")
            else:
                geom = shapely.wkt.loads(str(data['geometry']))
        else:
            scope = Scope.objects.get(pk=int(scope_id))
            geom = shapely.wkt.loads(scope.geom.wkt)
        response = {'intersection_area': []}
        fdate = data['from_date']
        edate = data['end_date']
        edate = datetime.strptime(edate, "%Y-%m-%d") + timedelta(days=31)
        for date in pd.date_range(
                fdate,
                edate,
                freq='M',
        ).strftime("%Y-%m"):
            response['intersection_area'].append(
                dict(date=date,
                     area=intersection_area_sql(
                         geom, datetime.strptime(date, '%Y-%m'))))
        return Response(response)


class AvailableDates(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        order_masks = VegetationMask.objects.all().order_by('period')
        if order_masks.count() > 0:
            response = {
                'first_date':
                order_masks.first().period.strftime('%Y-%m-%d %H:%M'),
                'last_date':
                order_masks.last().period.strftime('%Y-%m-%d %H:%M'),
                'availables':
                [mask.period.strftime('%Y-%m') for mask in order_masks]
            }
            return Response(response)
        else:
            return Response({
                'first_date': None,
                'last_date': None,
                'availables': []
            })


class ScopeTypes(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        response = []
        types = Scope.SCOPE_TYPE
        for key, name in types:
            s = dict(type=key, name=name, scopes=[])
            for scope in Scope.objects.filter(scope_type=key):
                s['scopes'].append(dict(name=scope.name, pk=scope.id))
            if len(s['scopes']) > 0:
                response.append(s)
        return Response(response)


class ScopeViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    queryset = Scope.objects.all()
    serializer_class = ScopeSerializer

    def get_queryset(self):
        queryset = Scope.objects.all()
        scope_type = self.request.query_params.get('type', None)
        if scope_type is not None:
            queryset = queryset.filter(scope_type=scope_type)
        return queryset
