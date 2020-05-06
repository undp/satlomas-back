from datetime import datetime
from django.contrib.auth.models import User
from django.shortcuts import render
from rest_framework import generics, mixins, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from alerts.models import Alert, ParameterRule, ScopeRule, ScopeTypeRule
from alerts.serializers import (AlertSerializer, ParameterRuleSerializer,
                                ScopeRuleSerializer, ScopeTypeRuleSerializer)


class ParameterRuleViewSet(viewsets.ModelViewSet):
    queryset = ParameterRule.objects.all().order_by('-created_at')
    serializer_class = ParameterRuleSerializer

    def get_queryset(self):
        return ParameterRule.objects.filter(
            user=self.request.user).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            print(serializer.errors)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=self.request.user)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data,
                        status=status.HTTP_201_CREATED,
                        headers=headers)


class ScopeRuleViewSet(viewsets.ModelViewSet):
    queryset = ScopeRule.objects.all().order_by('-created_at')
    serializer_class = ScopeRuleSerializer

    def get_queryset(self):
        return ScopeRule.objects.filter(
            user=self.request.user).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=self.request.user)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data,
                        status=status.HTTP_201_CREATED,
                        headers=headers)


class ScopeTypeRuleViewSet(viewsets.ModelViewSet):
    queryset = ScopeTypeRule.objects.all().order_by('-created_at')
    serializer_class = ScopeTypeRuleSerializer

    def get_queryset(self):
        return ScopeTypeRule.objects.filter(
            user=self.request.user).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=self.request.user)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data,
                        status=status.HTTP_201_CREATED,
                        headers=headers)


class AlertViewSet(viewsets.ModelViewSet):
    queryset = Alert.objects.all().order_by('created_at')
    serializer_class = AlertSerializer

    def get_queryset(self):
        return Alert.objects.filter(
            user=self.request.user).order_by('-created_at')


class LatestAlerts(APIView):

    def get(self, request):
        response = {'alerts':[]}
        alerts = Alert.objects.all().order_by('-created_at')
        if alerts.count() > 5:
            alerts = alerts[-5:0]
        [response['alerts'].append(alert.as_dict()) for alert in alerts]
        response['news'] = Alert.objects.filter(last_seen_at__isnull=True).count()
        return Response(response)


class SeenAlerts(APIView):

    def post(self, request):
        alerts = Alert.objects.filter(last_seen_at__isnull=True)
        for alert in alerts:
            alert.last_seen_at = datetime.now()
            alert.save()
        return Response({}, status=status.HTTP_204_NO_CONTENT)

