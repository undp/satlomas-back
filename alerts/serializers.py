from rest_framework import serializers
from rest_framework.fields import Field

from alerts.models import Alert, ParameterRule, ScopeRule, ScopeTypeRule
from stations.serializers import StationSerializer
from django.contrib.contenttypes.models import ContentType

from .models import COVERAGE_MEASUREMENT_MODELS, RULE_MODELS


class GenericRelatedField(Field):
    def __init__(self, queryset=None, *, related_field, **kwargs):
        super().__init__(**kwargs)
        self.related_field = related_field
        self.queryset = queryset or ContentType.objects.all()

    def to_internal_value(self, data):
        return ContentType.objects.filter(**{self.related_field: data}).first()

    def to_representation(self, obj):
        return getattr(obj, self.related_field)


class ParameterRuleSerializer(serializers.ModelSerializer):
    station = StationSerializer(read_only=True)

    class Meta:
        model = ParameterRule
        exclude = ('user', )


class ScopeRuleSerializer(serializers.ModelSerializer):
    measurement_content_type = GenericRelatedField(
        queryset=COVERAGE_MEASUREMENT_MODELS, related_field='app_label')

    class Meta:
        model = ScopeRule
        exclude = ('user', )


class ScopeTypeRuleSerializer(serializers.ModelSerializer):
    measurement_content_type = GenericRelatedField(
        queryset=COVERAGE_MEASUREMENT_MODELS, related_field='app_label')

    class Meta:
        model = ScopeTypeRule
        exclude = ('user', )


class AlertSerializer(serializers.ModelSerializer):
    rule_content_type = GenericRelatedField(queryset=RULE_MODELS,
                                            related_field='model')
    measurement_content_type = GenericRelatedField(
        queryset=COVERAGE_MEASUREMENT_MODELS, related_field='app_label')

    class Meta:
        model = Alert
        exclude = (
            'user',
            'measurement_id',
        )
