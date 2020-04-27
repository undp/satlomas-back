from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from alerts.models import Alert, ParameterRule, ScopeRule, ScopeTypeRule
from alerts.serializers import AlertSerializer, ParameterRuleSerializer, ScopeRuleSerializer, ScopeTypeRuleSerializer


class ParameterRuleViewSet(viewsets.ModelViewSet):
    queryset = ParameterRule.objects.all().order_by('-created_at')
    serializer_class = ParameterRuleSerializer


class ScopeRuleViewSet(viewsets.ModelViewSet):
    queryset = ScopeRule.objects.all().order_by('-created_at')
    serializer_class = ScopeRuleSerializer


class ScopeTypeRuleViewSet(viewsets.ModelViewSet):
    queryset = ScopeTypeRule.objects.all().order_by('-created_at')
    serializer_class = ScopeTypeRuleSerializer


class AlertViewSet(viewsets.ModelViewSet):
    queryset = Alert.objects.all().order_by('created_at')
    serializer_class = AlertSerializer