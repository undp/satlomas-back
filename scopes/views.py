from datetime import datetime

from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets

from vi_lomas_changes.models import Mask

from .models import Scope
from .serializers import ScopeSerializer


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
