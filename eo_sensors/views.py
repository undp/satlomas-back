import os
import shutil
import tempfile
from datetime import datetime
import shapely

from django.db import connection
from django.db.models import Q
from django.http import FileResponse
from jobs.utils import enqueue_job
from paramiko.ssh_exception import AuthenticationException
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotFound,
    PermissionDenied,
)
from rest_framework.response import Response
from rest_framework.views import APIView
from satlomas.renderers import BinaryFileRenderer

from .clients import SFTPClient
from .models import CoverageMask, CoverageMeasurement, Raster
from .serializers import (
    ImportSFTPListSerializer,
    ImportSFTPSerializer,
    RasterSerializer,
)


# @deprecated
def select_mask_areas_by_scope(**params):
    query = """
        SELECT m.id, m.kind, m.date, ST_Area(ST_Transform(
            ST_Intersection(m.geom, s.geom), %(srid)s)) AS area
        FROM (
            SELECT m.id, m.kind, m.geom, m.date
            FROM eo_sensors_coveragemask AS m
            WHERE m.date BETWEEN %(date_from)s AND %(date_to)s AND m.kind = %(kind)s
        ) AS m
        CROSS JOIN (SELECT geom FROM scopes_scope AS s WHERE s.id = %(scope_id)s) AS s
        """
    with connection.cursor() as cursor:
        cursor.execute(query, dict(srid=32718, **params))
        return [
            dict(id=id, kind=kind, date=date, area=area)
            for (id, kind, date, area) in cursor.fetchall()
        ]


def select_mask_areas_by_geom(**params):
    query = """
        SELECT m.id, m.kind, m.date, ST_Area(ST_Transform(
            ST_Intersection(m.geom, ST_GeomFromText(%(geom_wkt)s, 4326)), %(srid)s)) AS area
        FROM eo_sensors_coveragemask AS m
        WHERE m.date BETWEEN %(date_from)s AND %(date_to)s
        """
    with connection.cursor() as cursor:
        cursor.execute(query, dict(srid=32718, **params))
        return [
            dict(id=id, kind=kind, date=date, area=area)
            for (id, kind, date, area) in cursor.fetchall()
        ]


class CoverageView(APIView):
    permission_classes = [permissions.AllowAny]

    # TODO: Cache results?
    # @method_decorator(cache_page(60 * 60 * 24))  # 1 day
    # @method_decorator(vary_on_cookie)
    def get(self, request):
        params = request.query_params
        data = {
            k: params.get(k)
            for k in ("scope", "source", "kind", "geom", "date_from", "date_to")
            if k in params
        }

        if any(k not in data for k in ["source", "scope"]):
            raise APIException("Some parameters are missing (source or scope)")

        scope_id = int(data["scope"])
        source = data["source"]
        custom_geom = data["geom"] if "geom" in data else None
        date_from = datetime.strptime(data["date_from"], "%Y-%m-%d")
        date_to = datetime.strptime(data["date_to"], "%Y-%m-%d")

        values = []
        if custom_geom:
            geom = shapely.wkt.loads(custom_geom)
            values = select_mask_areas_by_geom(
                geom_wkt=geom.wkt,
                source=source,
                date_from=date_from,
                date_to=date_to,
            )
        else:
            values = (
                CoverageMeasurement.objects.filter(
                    source=source, date__range=(date_from, date_to), scope_id=scope_id
                )
                .order_by("date")
                .values("id", "kind", "date", "area")
            )

        return Response(dict(values=values))


class AvailableDatesView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        masks = CoverageMask.objects.all()

        source = request.query_params.get("source", None)
        if source:
            masks = masks.filter(source__in=source.split(",")).order_by("date")

        types = request.query_params.get("type", None)
        if types:
            masks = masks.filter(raster__slug__in=types.split(","))

        if masks.count() > 0:
            response = dict(
                first_date=masks.first().date,
                last_date=masks.last().date,
                availables=list(set([m.date for m in masks])),
            )
            return Response(response)
        else:
            return Response(dict(first_date=None, last_date=None, availables=[]))


class RasterViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Raster.objects.all().order_by("-created_at")
    serializer_class = RasterSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = self.queryset
        date_from = self.request.query_params.get("from", None)
        date_to = self.request.query_params.get("to", None)
        if date_from is not None and date_to is not None:
            queryset = queryset.filter(Q(date__gte=date_from) & Q(date__lte=date_to))
        slug = self.request.query_params.get("slug", None)
        if slug:
            queryset = queryset.filter(slug=slug)
        return queryset


class RasterDownloadView(APIView):
    renderer_classes = (BinaryFileRenderer,)

    def get(self, request, pk):
        file = Raster.objects.filter(pk=int(pk)).first()

        if not file:
            raise NotFound(detail=None, code=None)

        return self.try_download_file(file)

    def try_download_file(self, file):
        # Copy file from storage to a temporary file
        tmp = tempfile.NamedTemporaryFile(delete=False)
        shutil.copyfileobj(file.file, tmp)
        tmp.close()

        try:
            # Reopen temporary file as binary for streaming download
            stream_file = open(tmp.name, "rb")

            # Monkey patch .close method so that file is removed after closing it
            # i.e. when response finishes
            original_close = stream_file.close

            def new_close():
                original_close()
                os.remove(tmp.name)

            stream_file.close = new_close

            return FileResponse(stream_file, as_attachment=True, filename=file.name)
        except Exception as err:
            # Make sure to remove temp file
            os.remove(tmp.name)
            raise APIException(err)


class ImportSFTPListView(APIView):
    def post(self, request):
        serializer = ImportSFTPListSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        params = serializer.data
        path = params["path"] or "/"
        client = SFTPClient(
            hostname=params["hostname"],
            port=params["port"],
            username=params["username"],
            password=params["password"],
        )
        try:
            files = client.listdir(path)
        except PermissionError:
            raise PermissionDenied(detail=f"Listing {path} not allowed for user")
        except AuthenticationException:
            raise AuthenticationFailed()
        return Response(dict(values=files))


class ImportSFTPView(APIView):
    def post(self, request):
        serializer = ImportSFTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        params = serializer.data

        sftp_conn_info = {
            "hostname": params["hostname"],
            "port": params["port"],
            "username": params["username"],
            "password": params["password"],
        }

        for file in params["files"]:
            enqueue_job(
                "eo_sensors.tasks.perusat1.import_scene_from_sftp",
                sftp_conn_info=sftp_conn_info,
                file=file,
                queue="processing",
            )

        return Response({}, status=status.HTTP_204_NO_CONTENT)
