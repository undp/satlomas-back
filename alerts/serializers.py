from rest_framework import serializers
from alerts.models import Alert, ParameterRule, ScopeRule, ScopeTypeRule

class ParameterRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParameterRule
        exclude = ('user', )


class ScopeRuleSerializer(serializers.ModelSerializer):
    change_type = serializers.CharField(source='get_change_type_display')

    class Meta:
        model = ScopeRule
        exclude = ('user', )


class ScopeTypeRuleSerializer(serializers.ModelSerializer):
    change_type = serializers.CharField(source='get_change_type_display')
    scope_type = serializers.CharField(source='get_scope_type_display')
    measurement_content_type = serializers.SerializerMethodField('get_measurement_content_type')

    def get_measurement_content_type(self, instance):
        return instance.measurement_content_type.app_label

    class Meta:
        model = ScopeTypeRule
        exclude = ('user', )


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        exclude = ('user', )
