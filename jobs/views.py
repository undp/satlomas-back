from django.shortcuts import render
from rest_framework import viewsets

from jobs.models import Job, JobLogEntry
from jobs.serializers import JobLogEntrySerializer, JobSerializer


class JobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Job.objects.all().order_by('-finished_at', '-created_at')
    serializer_class = JobSerializer


class JobLogEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JobLogEntry.objects.all().order_by('-logged_at')
    serializer_class = JobLogEntrySerializer

    def get_queryset(self):
        return self.queryset.filter(job=self.kwargs['job_id'])