from django.shortcuts import render
from rest_framework import viewsets

from .serializers import ScopeSerializer


class ScopesViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Scope.objects.all()
    serializer_class = ScopeSerializer