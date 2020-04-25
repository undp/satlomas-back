from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.db import models

from scopes.models import Scope

# FIXME Move this to Settings
CHANGES_APPS = ['lomas_changes', 'vi_lomas_changes']

# FIXME generate based on CHANGES_APPS
COVERAGE_MEASUREMENT_MODELS = models.Q(
    app_label='lomas_changes', model='coveragemeasurement') | models.Q(
        app_label='vi_lomas_changes', model='coveragemeasurement')

RULE_MODELS = models.Q(model='scopetyperule') | models.Q(
    model='scoperule') | models.Q(model='parameterrule')

THRESHOLD_TYPES = [
    ('A', 'Area'),
    ('P', 'Percentage'),
]


class ScopeTypeRule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    scope_type = models.CharField(max_length=2, choices=Scope.SCOPE_TYPE)
    measurement_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=COVERAGE_MEASUREMENT_MODELS)
    threshold_type = models.CharField(max_length=1, choices=THRESHOLD_TYPES)
    threshold = models.FloatField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '{m_type} {t_type} > {threshold} ({scope_type})'.format(
            m_type=self.measurement_content_type,
            t_type=self.get_threshold_type_display(),
            threshold=self.threshold,
            scope_type=self.scope_type)


class ScopeRule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    scope = models.ForeignKey('scopes.Scope', on_delete=models.CASCADE)
    measurement_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=COVERAGE_MEASUREMENT_MODELS)
    threshold_type = models.CharField(max_length=1, choices=THRESHOLD_TYPES)
    threshold = models.FloatField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '{m_type} {t_type} > {threshold} ({scope})'.format(
            m_type=self.measurement_content_type,
            t_type=self.get_threshold_type_display(),
            threshold=self.threshold,
            scope=self.scope.name)


class ParameterRule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    station = models.ForeignKey('stations.Station',
                                on_delete=models.CASCADE,
                                null=True,
                                blank=True)
    parameter = models.CharField(max_length=64)
    threshold = models.FloatField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'station', 'parameter']

    def __str__(self):
        station_s = self.station.name if self.station else 'cualquier estación'
        return '{parameter} > {threshold} ({station})'.format(
            parameter=self.parameter,
            threshold=self.threshold,
            station=station_s)


class Alert(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rule_content_type = models.ForeignKey(ContentType,
                                          on_delete=models.CASCADE,
                                          related_name="%(class)s_related",
                                          limit_choices_to=RULE_MODELS)
    rule_id = models.PositiveIntegerField()
    rule = GenericForeignKey('rule_content_type', 'rule_id')

    measurement_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=COVERAGE_MEASUREMENT_MODELS)
    measurement_id = models.PositiveIntegerField()
    measurement = GenericForeignKey('measurement_content_type',
                                    'measurement_id')

    created_at = models.DateTimeField(auto_now_add=True)