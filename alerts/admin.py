from django import forms
from django.contrib import admin

from .models import Alert, ParameterRule, ScopeRule, ScopeTypeRule


class FilterUserAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        obj.user = request.user
        obj.save()

    def get_queryset(self, request):
        # For Django < 1.6, override queryset instead of get_queryset
        qs = super(FilterUserAdmin, self).get_queryset(request)
        return qs.filter(user=request.user)

    def has_change_permission(self, request, obj=None):
        if not obj:
            # the changelist itself
            return True
        return obj.user == request.user


class ParameterRuleForm(forms.ModelForm):
    PARAMETERS = (
        ('temperature', 'Temperatura'),
        ('humidity', 'Humedad Relativa'),
        ('wind_speed', 'Velocidad del Viento'),
        ('wind_direction', 'Dirección del Viento'),
        ('pressure', 'Presión Atmosférica'),
        ('precipitation', 'Precipitación'),
        ('pm25', 'Material particulado (pm25)'),
    )

    parameter = forms.ChoiceField(choices=PARAMETERS)


class ParameterRuleAdmin(FilterUserAdmin):
    list_display = [
        'station', 'parameter', 'threshold', 'created_at', 'updated_at'
    ]
    exclude = ('user', )
    form = ParameterRuleForm


class ScopeRuleAdmin(FilterUserAdmin):
    list_display = [
        'scope', 'measurement_content_type', 'threshold_type', 'threshold',
        'created_at', 'updated_at'
    ]
    exclude = ('user', )


class ScopeTypeRuleAdmin(FilterUserAdmin):
    list_display = [
        'scope_type', 'measurement_content_type', 'threshold_type',
        'threshold', 'created_at', 'updated_at'
    ]
    exclude = ('user', )


class AlertAdmin(FilterUserAdmin):
    list_display = [
        'created_at',
        'rule_content_type',
        'rule_id',
        'rule',
        'measurement_content_type',
        'measurement_id',
        'measurement',
    ]
    exclude = ('user', )


admin.site.register(ParameterRule, ParameterRuleAdmin)
admin.site.register(ScopeRule, ScopeRuleAdmin)
admin.site.register(ScopeTypeRule, ScopeTypeRuleAdmin)
admin.site.register(Alert, AlertAdmin)
