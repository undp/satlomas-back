from rest_framework import serializers

from jobs.models import Job, JobLogEntry


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ('id', 'name', 'args', 'kwargs', 'state', 'created_at',
                  'finished_at', 'updated_at', 'metadata', 'duration', 'error',
                  'estimated_duration')


class JobLogEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = JobLogEntry
        fields = '__all__'