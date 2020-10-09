import json

from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html

from jobs.models import Job, JobLogEntry


class JobAdmin(admin.ModelAdmin):
    """Admin-interface for jobs"""

    model = Job
    date_hierarchy = 'finished_at'
    list_display = (
        'id',
        'name',
        'arguments',
        'keyword_arguments',
        'state',
        'created_at',
        'finished_at',
    )
    list_display_links = ('id', 'name')
    list_filter = (
        'state',
        'finished_at',
        'name',
    )
    search_fields = ('name', 'id', 'status')

    def arguments(self, instance):
        return format_html('<pre style="margin: 0">{}</pre>',
                           json.dumps(instance.args, indent=4, sort_keys=True))

    def keyword_arguments(self, instance):
        return format_html(
            '<pre style="margin: 0">{}</pre>',
            json.dumps(instance.kwargs, indent=4, sort_keys=True))


class JobLogEntryAdmin(admin.ModelAdmin):
    model = JobLogEntry
    date_hierarchy = 'logged_at'
    list_display = (
        'logged_at',
        'job',
    )
    list_filter = ('job', )
    ordering = ['-logged_at']


admin.site.register(Job, JobAdmin)
admin.site.register(JobLogEntry, JobLogEntryAdmin)
