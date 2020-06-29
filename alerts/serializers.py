import lomas_changes.models
import lomas_changes.serializers
import stations.models
import stations.serializers
import vi_lomas_changes.models
import vi_lomas_changes.serializers
from alerts.models import (Alert, ParameterRule, ScopeRule, ScopeTypeRule,
                           UserProfile)
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers
from rest_framework.fields import Field
from stations.serializers import StationSerializer

from .models import (COVERAGE_MEASUREMENT_MODELS, MEASUREMENT_MODELS,
                     RULE_MODELS)


class GenericRelatedField(Field):
    def __init__(self, queryset=None, *, related_field, **kwargs):
        super().__init__(**kwargs)
        self.related_field = related_field
        self.queryset = queryset or ContentType.objects.all()

    def to_internal_value(self, data):
        return ContentType.objects.filter(**{self.related_field: data}).first()

    def to_representation(self, obj):
        return getattr(obj, self.related_field)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.SlugRelatedField(read_only=True,
                                            source='user',
                                            slug_field='username')

    class Meta:
        model = UserProfile
        fields = ('email_alerts', 'username')


class ParameterRuleSerializer(serializers.ModelSerializer):
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


class GenericSerializer(serializers.BaseSerializer):
    classes = []

    def to_representation(self, instance):
        for model_class, serializer_class in self.classes:
            if isinstance(instance, model_class):
                return serializer_class().to_representation(instance)

    def to_internal_value(self, data):
        raise ValueError("RuleSerializer is a read-only serializer")


class GenericRuleSerializer(GenericSerializer):
    classes = [
        (ScopeTypeRule, ScopeTypeRuleSerializer),
        (ScopeRule, ScopeRuleSerializer),
        (ParameterRule, ParameterRuleSerializer),
    ]


class GenericMeasurementSerializer(GenericSerializer):
    classes = [
        (lomas_changes.models.CoverageMeasurement,
         lomas_changes.serializers.CoverageMeasurementSerializer),
        (vi_lomas_changes.models.CoverageMeasurement,
         vi_lomas_changes.serializers.CoverageMeasurementSerializer),
        (stations.models.Measurement,
         stations.serializers.MeasurementSerializer),
    ]


class AlertSerializer(serializers.ModelSerializer):
    rule_content_type = GenericRelatedField(queryset=RULE_MODELS,
                                            related_field='model')
    rule = GenericRuleSerializer()
    measurement_content_type = GenericRelatedField(queryset=MEASUREMENT_MODELS,
                                                   related_field='app_label')
    measurement = GenericMeasurementSerializer()
    rule_attributes = serializers.JSONField()

    description = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        exclude = (
            'user',
            'rule_id',
            'measurement_id',
        )
    
    def get_description(self, obj):
        return obj.describe()
