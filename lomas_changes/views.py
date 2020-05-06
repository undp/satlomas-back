import mimetypes
import os
import shutil
import tempfile
from django.db.models import Q
from django.http import FileResponse
from geolomas.renderers import BinaryFileRenderer
from rest_framework import permissions, viewsets
from rest_framework.views import APIView
from .models import Raster
from .serializers import RasterSerializer

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


class RasterDownloadView(APIView):
    renderer_classes = (BinaryFileRenderer, )

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
            stream_file = open(tmp.name, 'rb')

            # Monkey patch .close method so that file is removed after closing it
            # i.e. when response finishes
            original_close = stream_file.close
            def new_close():
                original_close()
                os.remove(tmp.name)
            stream_file.close = new_close

            return FileResponse(stream_file,
                                as_attachment=True,
                                filename=file.name)
        except Exception as err:
            # Make sure to remove temp file
            os.remove(tmp.name)
            raise APIException(err)