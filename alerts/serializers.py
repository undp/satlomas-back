from rest_framework import serializers
from alerts.models import ParameterRule, ScopeRule, ScopeTypeRule

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