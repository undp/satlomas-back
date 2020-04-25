from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.db import models

from scopes.models import Scope

# FIXME Move this to Settings
CHANGES_APPS = ['lomas_changes', 'vi_lomas_changes']
# FIXME generate based on CHANGES_APPS
LIMITS = models.Q(
    app_label='lomas_changes', model='coverage_measurements') | models.Q(
        app_label='vi_lomas_changes', model='coverage_measurements')

THRESHOLD_TYPES = [
    ('A', 'Area'),
    ('P', 'Percentage'),
]


class ScopeTypeRule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    scope_type = models.CharField(max_length=2, choices=Scope.SCOPE_TYPE)
    measurement_content_type = models.ForeignKey(ContentType,
                                                 on_delete=models.CASCADE,
                                                 limit_choices_to=LIMITS)
    threshold_type = models.CharField(max_length=1, choices=THRESHOLD_TYPES)
    threshold = models.FloatField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ScopeRule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    scope = models.ForeignKey('scopes.Scope', on_delete=models.CASCADE)
    measurement_content_type = models.ForeignKey(ContentType,
                                                 on_delete=models.CASCADE,
                                                 limit_choices_to=LIMITS)
    threshold_type = models.CharField(max_length=1, choices=THRESHOLD_TYPES)
    threshold = models.FloatField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


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


# class Alert(models.Model):
#     rule_content_type = models.ForeignKey(ContentType,
#                                           on_delete=models.CASCADE)
#     rule_id = models.PositiveIntegerField()
#     rule = GenericForeignKey('rule_content_type', 'rule_id')

#     measurement_content_type = models.ForeignKey(ContentType,
#                                                  on_delete=models.CASCADE)
#     measurement_id = models.PositiveIntegerField()
#     measurement = GenericForeignKey('measurement_content_type',
#                                     'measurement_id')
