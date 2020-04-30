from datetime import datetime, timedelta

import pandas as pd
import shapely.wkt
from django.db import connection
from django.db.models import Q
from django.shortcuts import render
from rest_framework import permissions, viewsets
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from scopes.models import Scope

from .models import Mask, Period


def intersection_area_sql(scope_geom, period):
    mask = Mask.objects.filter(period=period, mask_type='ndvi').first()
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
            FROM vi_lomas_changes_mask AS m
            INNER JOIN vi_lomas_changes_period AS p ON m.period_id = p.id
            WHERE p.date_to BETWEEN %(date_from)s AND %(date_to)s AND m.mask_type = %(mask_type)s
        ) AS m
        CROSS JOIN (SELECT geom FROM scopes_scope AS s WHERE s.id = %(scope_id)s) AS s
        """
    with connection.cursor() as cursor:
        cursor.execute(query, dict(srid=32718, mask_type='ndvi', **params))
        return [
            dict(id=id, date=date, area=area)
            for (id, date, area) in cursor.fetchall()
        ]


def select_mask_areas_by_geom(**params):
    query = """
        SELECT m.id, m.date_to, ST_Area(ST_Transform(
            ST_Intersection(m.geom, ST_GeomFromText(%(geom_wkt)s, 4326)), %(srid)s)) AS area
        FROM vi_lomas_changes_mask AS m
        INNER JOIN vi_lomas_changes_period AS p ON m.period_id = p.id
        WHERE p.date_to BETWEEN %(date_from)s AND %(date_to)s AND m.mask_type = %(mask_type)s
        """
    with connection.cursor() as cursor:
        cursor.execute(query, dict(srid=32718, mask_type='ndvi', **params))
        return [
            dict(id=id, date=date, area=area)
            for (id, date, area) in cursor.fetchall()
        ]


class TimeSeries(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data

        scope_id = int(data['scope_id']) if 'scope_id' in data else None
        custom_geom = data['geom'] if 'geom' in data else None

        if scope_id is None and custom_geom is None:
            raise APIException(
                "Either 'scope_id' or 'geom' parameters are missing")

        date_from = datetime.strptime(data['from_date'], "%Y-%m-%d")
        date_to = datetime.strptime(data['end_date'], "%Y-%m-%d")

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

    def get(self, request):
        masks = Mask.objects.all().order_by('period__date_from')
        if masks.count() > 0:
            response = dict(first_date=masks.first().period.date_from,
                            last_date=masks.last().period.date_to,
                            availables=[(m.period.date_from, m.period.date_to)
                                        for m in masks])
            return Response(response)
        else:
            return Response(
                dict(first_date=None, last_date=None, availables=[]))
