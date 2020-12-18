from datetime import datetime

import pytz
from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from alerts import CHANGE_APPS
from alerts.models import (Alert, AlertCheck, ParameterRule, ScopeRule,
                           ScopeTypeRule)


def timezone_min():
    if settings.USE_TZ:
        return datetime.min.replace(tzinfo=pytz.utc)
    else:
        return datetime.min


class Command(BaseCommand):
    help = 'Check for new Alerts and trigger them'

    @transaction.atomic
    def handle(self, *args, **options):
        self.process_parameter_rules()
        self.process_scope_type_rules()
        self.process_scope_rules()

    def process_parameter_rules(self):
        start, end = self.create_alert_check()
        self.log_success(
            f"Checking for new measurements from {start} to {end}")

        measurement_class = apps.get_model(app_label='stations',
                                           model_name='measurement')
        measurements = measurement_class.objects.with_prev_attributes().filter(
            datetime__gte=start, datetime__lt=end)
        self.log_success(
            f"There are {measurements.count()} new measurements to analyze")

        rules = ParameterRule.objects.all()
        self.log_success(f"There are {len(rules)} Parameter rules")
        for rule in rules:
            self.log_success(f"ParameterRule: {rule}")
            if rule.station:
                measurements = measurements.filter(station=rule.station)
            self.verify_rule_with(measurements, rule=rule)

    def process_scope_type_rules(self):
        for app_label in CHANGE_APPS:
            start, end = self.create_alert_check()
            self.log_success(
                f"Checking for new measurements from {start} to {end}")

            # Get measurements so that their periods overlap with start..end
            coverage_measurement_class = apps.get_model(
                app_label=app_label, model_name='coveragemeasurement')
            measurements = coverage_measurement_class.objects.filter(
                created_at__gte=start, created_at__lt=end)
            self.log_success(
                f"[{app_label}] There are {measurements.count()} new coverage measurements to analyze"
            )

            rules = ScopeTypeRule.objects.filter(
                measurement_content_type__app_label=app_label).all()
            self.log_success(f"There are {len(rules)} ScopeType rules")

            for rule in rules:
                self.log_success(f"ScopeTypeRule: {rule}")
                if rule.scope_type:
                    measurements = measurements.filter(
                        scope__scope_type=rule.scope_type)
                self.verify_rule_with(measurements, rule=rule)

    def process_scope_rules(self):
        for app_label in CHANGE_APPS:
            kwargs = dict()
            start, end = self.create_alert_check()
            self.log_success(
                f"Checking for new measurements from {start} to {end}")

            # Get measurements so that their periods overlap with start..end
            coverage_measurement_class = apps.get_model(
                app_label=app_label, model_name='coveragemeasurement')
            measurements = coverage_measurement_class.objects.filter(
                created_at__gte=start, created_at__lt=end)
            self.log_success(
                f"[{app_label}] There are {measurements.count()} new coverage measurements to analyze"
            )

            rules = ScopeRule.objects.filter(
                measurement_content_type__app_label=app_label).all()
            self.log_success(f"There are {len(rules)} ScopeType rules")

            for rule in rules:
                self.log_success(f"ScopeRule: {rule}")
                if rule.scope:
                    measurements = measurements.filter(scope=rule.scope)
                self.verify_rule_with(measurements, rule=rule)

    def verify_rule_with(self, measurements, *, rule):
        for m in measurements:
            if rule.is_absolute:
                value = m.attributes[rule.parameter]
            else:
                prev_value = m.prev_attributes[
                    rule.parameter] if m.prev_attributes else 0.0
                value = m.attributes[rule.parameter] - prev_value
            if value < rule.valid_min or value > rule.valid_max:
                print(value, rule.get_valid_range_display())
                self.create_alert(measurement=m, rule=rule, value=value)

    def create_alert(self, *, rule, measurement, value):
        alert = Alert.objects.create(user=rule.user,
                                     rule=rule,
                                     measurement=measurement,
                                     value=value)
        self.log_success(f"New Alert: {alert}")
        return alert

    def create_alert_check(self):
        last_check = AlertCheck.objects.last()
        start = last_check.created_at if last_check else timezone_min()
        current_check = AlertCheck.objects.create()
        end = current_check.created_at
        return start, end

    def log_success(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    def log_error(self, msg):
        self.stderr.write(self.style.ERROR(msg))
