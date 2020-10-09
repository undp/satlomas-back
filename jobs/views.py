from django.shortcuts import render
from rest_framework import pagination, viewsets

from jobs.models import Job, JobLogEntry
from jobs.serializers import JobLogEntrySerializer, JobSerializer


class JobPagination(pagination.PageNumberPagination):
    page_size = 20


class JobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Job.objects.all().order_by('-finished_at', '-created_at')
    serializer_class = JobSerializer
    pagination_class = JobPagination


class JobLogEntryPagination(pagination.PageNumberPagination):
    page_size = 100


class JobLogEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JobLogEntry.objects.all().order_by('-logged_at')
    serializer_class = JobLogEntrySerializer
    pagination_class = JobLogEntryPagination

    def get_queryset(self):
        return self.queryset.filter(job=self.kwargs['job_id'])
