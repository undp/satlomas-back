from rest_framework import serializers

from jobs.models import Job


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ('id', 'name', 'args', 'kwargs', 'state', 'created_at',
                  'finished_at', 'updated_at', 'metadata', 'duration', 'error',
                  'estimated_duration')
