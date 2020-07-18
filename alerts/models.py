import json

from auditlog.registry import auditlog
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import JSONField
from django.db import models

from scopes.models import Scope

# FIXME Move this to Settings
CHANGE_APPS = ['lomas_changes', 'vi_lomas_changes']

# FIXME generate based on CHANGE_APPS
COVERAGE_MEASUREMENT_MODELS = models.Q(
    app_label='lomas_changes', model='coveragemeasurement') | models.Q(
        app_label='vi_lomas_changes', model='coveragemeasurement')
MEASUREMENT_MODELS = COVERAGE_MEASUREMENT_MODELS | models.Q(
    app_label='stations', model='measurement')

RULE_MODELS = models.Q(model='scopetyperule') | models.Q(
    model='scoperule') | models.Q(model='parameterrule')

CHANGE_TYPES = [
    ('A', 'Area'),
    ('P', 'Percentage'),
]


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email_alerts = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ScopeTypeRule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    scope_type = models.CharField(max_length=2, choices=Scope.SCOPE_TYPE)
    measurement_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=COVERAGE_MEASUREMENT_MODELS)
    change_type = models.CharField(max_length=1, choices=CHANGE_TYPES)
    is_absolute = models.BooleanField(default=False)
    valid_min = models.FloatField(default=-5)
    valid_max = models.FloatField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '{m_type} {c_type} {valid_range} ({scope_type})'.format(
            m_type=self.measurement_content_type,
            c_type=self.get_change_type_display(),
            valid_range=self.get_valid_range_display(),
            scope_type=self.scope_type)

    def get_valid_range_display(self):
        return f'{self.valid_min} - {self.valid_max}'

    def serialize(self):
        return json.dumps(
            dict(scope_type=self.scope_type,
                 measurement_content_type_str=str(
                     self.measurement_content_type),
                 change_type=self.change_type,
                 valid_min=self.valid_min,
                 valid_max=self.valid_max))


class ScopeRule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    scope = models.ForeignKey('scopes.Scope', on_delete=models.CASCADE)
    measurement_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=COVERAGE_MEASUREMENT_MODELS)
    change_type = models.CharField(max_length=1, choices=CHANGE_TYPES)
    is_absolute = models.BooleanField(default=False)
    valid_min = models.FloatField(default=-5)
    valid_max = models.FloatField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '{m_type} {c_type} {valid_range} ({scope})'.format(
            m_type=self.measurement_content_type,
            c_type=self.get_change_type_display(),
            valid_range=self.get_valid_range_display(),
            scope=self.scope.name)

    def get_valid_range_display(self):
        return f'{self.valid_min} - {self.valid_max}'

    def serialize(self):
        return json.dumps(
            dict(scope_id=self.scope and self.scope.pk,
                 scope_name=self.scope and self.scope.name,
                 scope_type=self.scope and self.scope.scope_type,
                 measurement_content_type_str=str(
                     self.measurement_content_type),
                 change_type=self.change_type,
                 valid_min=self.valid_min,
                 valid_max=self.valid_max))


class ParameterRule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    station = models.ForeignKey('stations.Station',
                                on_delete=models.CASCADE,
                                null=True,
                                blank=True)
    parameter = models.CharField(max_length=64)
    is_absolute = models.BooleanField(default=False)
    valid_min = models.FloatField(default=-5)
    valid_max = models.FloatField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'station', 'parameter']

    def __str__(self):
        station_s = self.station.name if self.station else 'cualquier estación'
        abs_s = ' (absoluto)' if self.is_absolute else ''
        valid_range = self.get_valid_range_display()
        return f'{self.parameter}{abs_s} {valid_range} ({station_s})'

    def get_valid_range_display(self):
        return f'{self.valid_min} - {self.valid_max}'

    def serialize(self):
        return json.dumps(
            dict(station_id=self.station and self.station.id,
                 station_name=self.station and self.station.name,
                 parameter=self.parameter,
                 is_absolute=self.is_absolute,
                 valid_min=self.valid_min,
                 valid_max=self.valid_max))


class AlertCheck(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)


class Alert(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rule_content_type = models.ForeignKey(ContentType,
                                          on_delete=models.CASCADE,
                                          related_name="%(class)s_related",
                                          limit_choices_to=RULE_MODELS)
    rule_id = models.PositiveIntegerField()
    rule = GenericForeignKey('rule_content_type', 'rule_id')
    rule_attributes = JSONField(default=dict)

    measurement_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=MEASUREMENT_MODELS)
    measurement_id = models.PositiveIntegerField()
    measurement = GenericForeignKey('measurement_content_type',
                                    'measurement_id')

    value = models.FloatField(null=True)

    last_seen_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        t = self.created_at
        r_type = self.rule_content_type
        m_type = self.measurement_content_type
        return f'{t} :: {r_type}.{self.rule} :: {m_type}.{self.measurement}'

    def save(self, *args, **kwargs):
        # Get rule attributes before saving, for historical purposes
        # If related rule is modified in the future, original attributes are
        # preserved in this field.
        self.rule_attributes = json.loads(self.rule.serialize())
        super().save(*args, **kwargs)

    def describe(self):
        value = self.value
        if value is None:
            return ''

        if value > 0:
            changeVerb = 'aumentó'
            changeVerb2 = 'mayor'
            threshValue = self.rule_attributes['valid_max']
        else:
            changeVerb = 'disminuyó'
            changeVerb2 = 'menor'
            threshValue = self.rule_attributes['valid_min']

        if self.rule_content_type.name == "parameter rule":
            parameterName = self.rule_attributes['parameter']
            station_name = self.rule_attributes['station_name']
            return f'El parámetro {parameterName} de la estación {station_name} {changeVerb} {abs(value)}, {changeVerb2} que el umbral {abs(threshValue)}.'
        
        elif self.rule_content_type.name == "scope type rule":
            scopeType = self.rule_attributes['scope_type']
            change_type = self.rule_attributes['change_type']
            if change_type == "A":
                return f'El área en todos los ámbitos de {scopeType} {changeVerb} {abs(value)} has, {changeVerb2} que el umbral de {abs(threshValue)} has.'
            elif change_type == "P":
                return f'El porcentaje de área en todos los ámbitos de {scopeType} {changeVerb} {abs(value)} has, {changeVerb2} que el umbral de {abs(threshValue)} has.'
            else:
                change_type = self.rule_attributes['change_type']
                raise Exception(f'Unknown change type {change_type}.')
        
        elif self.rule_content_type.name == "scope rule":
            scopeName = self.rule_attributes['scope_name']
            scopeType = self.rule_attributes['scope_type']
            change_type = self.rule_attributes['change_type']
            if change_type == "A":
                return f'El área del ámbito {scopeName} ({scopeType}) {changeVerb} {abs(value)} has, {changeVerb2} que el umbral de {abs(threshValue)} has.'
            elif change_type == "P":
                return f'El porcentaje de área del ámbito {scopeName} ({scopeType}) {changeVerb} {abs(value)} has, {changeVerb2} que el umbral de {abs(threshValue)} has.'
            else:
                change_type = self.rule_attributes['change_type']
                raise Exception(f'Unknown change type {change_type}.')

        else:
            
            raise Exception(f'Unknown rule content type {self.rule_content_type}.')



auditlog.register(ScopeTypeRule)
auditlog.register(ScopeRule)
auditlog.register(ParameterRule)
auditlog.register(Alert, include_fields=['last_seen'])
auditlog.register(UserProfile)
