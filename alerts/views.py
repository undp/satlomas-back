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

    def get_queryset(self):
        return ParameterRule.objects.filter(user=self.request.user).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=self.request.user)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class ScopeRuleViewSet(viewsets.ModelViewSet):
    queryset = ScopeRule.objects.all().order_by('-created_at')
    serializer_class = ScopeRuleSerializer

    def get_queryset(self):
        return ScopeRule.objects.filter(user=self.request.user).order_by('-created_at')
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=self.request.user)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class ScopeTypeRuleViewSet(viewsets.ModelViewSet):
    queryset = ScopeTypeRule.objects.all().order_by('-created_at')
    serializer_class = ScopeTypeRuleSerializer

    def get_queryset(self):
        return ScopeTypeRule.objects.filter(user=self.request.user).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=self.request.user)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class AlertViewSet(viewsets.ModelViewSet):
    queryset = Alert.objects.all().order_by('created_at')
    serializer_class = AlertSerializer

    def get_queryset(self):
        return Alert.objects.filter(user=self.request.user).order_by('-created_at')