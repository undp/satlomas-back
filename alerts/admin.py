from django.contrib import admin

from .models import ParameterRule, ScopeRule, ScopeTypeRule

admin.site.register(ParameterRule)
admin.site.register(ScopeRule)
admin.site.register(ScopeTypeRule)
