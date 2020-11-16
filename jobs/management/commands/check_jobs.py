import sys
from datetime import datetime

import django_rq
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Exits succesfully if there are jobs on queue or being currently executing'

    def add_arguments(self, parser):
        parser.add_argument('--queue',
                            '-Q',
                            required=True,
                            help='queue to check')

    def handle(self, *args, **options):
        queue = django_rq.get_queue(options['queue'])
        if len(queue.jobs) > 0 or queue.started_job_registry.count > 0:
            sys.exit(0)
        else:
            sys.exit(1)
