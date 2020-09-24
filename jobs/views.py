from django.shortcuts import render
from rest_framework import viewsets

from jobs.models import Job
from jobs.serializers import JobSerializer


class JobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Job.objects.all().order_by('-finished_at', '-created_at')
    serializer_class = JobSerializer
