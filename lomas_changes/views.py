from datetime import datetime, timedelta

import pandas as pd
import shapely.wkt
from django.db import connection
from django.db.models import Q
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from rest_framework import permissions, viewsets
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from scopes.models import Scope

from .models import Mask, Period, Raster
from .serializers import RasterSerializer


def intersection_area_sql(scope_geom, period):
    mask = Mask.objects.filter(period=period, mask_type='loss').first()
    query = """SELECT ST_Area(a.int) AS area
               FROM (
                   SELECT ST_Intersection(
                       ST_Transform(ST_GeomFromText('{wkt_scope}', 4326), {srid}),
                       ST_Transform(ST_GeomFromText('{wkt_mask}', 4326), {srid})) AS int) a;
            """.format(wkt_scope=scope_geom.wkt, wkt_mask=mask.geom.wkt)
    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()[0][0]


def select_mask_areas_by_scope(**params):
    query = """
        SELECT m.id, m.date_to, ST_Area(ST_Transform(
            ST_Intersection(m.geom, s.geom), %(srid)s)) AS area
        FROM (
            SELECT m.id, m.geom, p.date_to
            FROM lomas_changes_mask AS m
            INNER JOIN lomas_changes_period AS p ON m.period_id = p.id
            WHERE p.date_to BETWEEN %(date_from)s AND %(date_to)s AND m.mask_type = %(mask_type)s
        ) AS m
        CROSS JOIN (SELECT geom FROM scopes_scope AS s WHERE s.id = %(scope_id)s) AS s
        """
    with connection.cursor() as cursor:
        cursor.execute(query, dict(srid=32718, mask_type='loss', **params))
        return [
            dict(id=id, date=date, area=area)
            for (id, date, area) in cursor.fetchall()
        ]


def select_mask_areas_by_geom(**params):
    query = """
        SELECT m.id, m.date_to, ST_Area(ST_Transform(
            ST_Intersection(m.geom, ST_GeomFromText(%(geom_wkt)s, 4326)), %(srid)s)) AS area
        FROM lomas_changes_mask AS m
        INNER JOIN lomas_changes_period AS p ON m.period_id = p.id
        WHERE p.date_to BETWEEN %(date_from)s AND %(date_to)s AND m.mask_type = %(mask_type)s
        """
    with connection.cursor() as cursor:
        cursor.execute(query, dict(srid=32718, mask_type='loss', **params))
        return [
            dict(id=id, date=date, area=area)
            for (id, date, area) in cursor.fetchall()
        ]


class TimeSeries(APIView):
    permission_classes = [permissions.AllowAny]

    @method_decorator(cache_page(60 * 60 * 24))  # 1 day
    @method_decorator(vary_on_cookie)
    def get(self, request):
        params = request.query_params
        data = {
            k: params.get(k)
            for k in ('scope', 'geom', 'date_from', 'date_to') if k in params
        }

        scope_id = int(data['scope']) if 'scope' in data else None
        custom_geom = data['geom'] if 'geom' in data else None

        if scope_id is None and custom_geom is None:
            raise APIException(
                "Either 'scope' or 'geom' parameters are missing")

        date_from = datetime.strptime(data['date_from'], "%Y-%m-%d")
        date_to = datetime.strptime(data['date_to'], "%Y-%m-%d")

        values = []
        if custom_geom:
            geom = shapely.wkt.loads(custom_geom)
            values = select_mask_areas_by_geom(geom_wkt=geom.wkt,
                                               date_from=date_from,
                                               date_to=date_to)
        else:
            values = select_mask_areas_by_scope(scope_id=scope_id,
                                                date_from=date_from,
                                                date_to=date_to)

        return Response(dict(values=values))


class AvailablePeriods(APIView):
    permission_classes = [permissions.AllowAny]

    @method_decorator(cache_page(60 * 60 * 2))  # 2 hours
    @method_decorator(vary_on_cookie)
    def get(self, request):
        masks = Mask.objects.all().order_by('period__date_to')
        if masks.count() > 0:
            periods = [m.period for m in masks]
            periods = sorted(list(
                set([(p.id, p.date_from, p.date_to) for p in periods])),
                             key=lambda x: x[2])
            periods = [
                dict(id=id, date_from=date_from, date_to=date_to)
                for id, date_from, date_to in periods
            ]
            response = dict(first_date=masks.first().period.date_from,
                            last_date=masks.last().period.date_to,
                            availables=periods)
            return Response(response)
        else:
            return Response(
                dict(first_date=None, last_date=None, availables=[]))


class RasterViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Raster.objects.all().order_by('-created_at')
    serializer_class = RasterSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = self.queryset
        date_from = self.request.query_params.get('from', None)
        date_to = self.request.query_params.get('to', None)
        if date_from is not None and date_to is not None:
            queryset = queryset.filter(
                Q(period__date_from=date_from)
                | Q(period__date_to=date_to))
        return queryset
