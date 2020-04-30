"""geolomas URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import url
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions
from rest_framework.routers import SimpleRouter

from alerts.views import (AlertViewSet, ParameterRuleViewSet, ScopeRuleViewSet,
                          ScopeTypeRuleViewSet)

schema_view = get_schema_view(
    openapi.Info(
        title='GeoLomas API',
        default_version='v1',
        description='This is the description of the API',
        terms_of_service='[add link to tos]',
        contact=openapi.Contact(email='contact@dymaxionlabs.com'),
        license=openapi.License(name='BSD License'),
    ),
    public=True,
    permission_classes=(permissions.AllowAny, ),
)

swagger_urls = [
    # Documentation
    url(r'^swagger(?P<format>\.json|\.yaml)$',
        schema_view.without_ui(cache_timeout=0),
        name='schema-json'),
    url(r'^swagger/$',
        schema_view.with_ui('swagger', cache_timeout=0),
        name='schema-swagger-ui'),
    url(r'^redoc/$',
        schema_view.with_ui('redoc', cache_timeout=0),
        name='schema-redoc'),
]

router = SimpleRouter()
router.register(r'parameter-rules', ParameterRuleViewSet)
router.register(r'scopes-rules', ScopeRuleViewSet)
router.register(r'scopes-type-rule', ScopeTypeRuleViewSet)
router.register(r'alerts', AlertViewSet)

urlpatterns = [
    url(r'^api-auth/', include('rest_framework.urls')),

    # Authentication
    url(r'^auth/', include('rest_auth.urls')),

    # Administration
    url(r'^admin/', admin.site.urls),
]

# API documentation only if DEBUG=1
if settings.DEBUG:
    urlpatterns += swagger_urls

urlpatterns += [path('vi-lomas/', include('vi_lomas_changes.urls'))]
urlpatterns += [path('stations/', include('stations.urls'))]
urlpatterns += [path('scopes/', include('scopes.urls'))]
urlpatterns += router.urls

urlpatterns += [path('admin/django-rq/', include('django_rq.urls'))]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
