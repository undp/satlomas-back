from rest_framework import serializers
from alerts.models import Alert, ParameterRule, ScopeRule, ScopeTypeRule

class ParameterRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParameterRule
        exclude = ('user', )


class ScopeRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScopeRule
        exclude = ('user', )


class ScopeTypeRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScopeTypeRule
        exclude = ('user', )


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        exclude = ('user', )
