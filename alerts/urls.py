from django.conf.urls import url
from django.urls import include
from rest_framework.routers import SimpleRouter

from alerts import views

router = SimpleRouter()
router.register(r'parameter-rules', views.ParameterRuleViewSet)
router.register(r'scope-rules', views.ScopeRuleViewSet)
router.register(r'scope-type-rule', views.ScopeTypeRuleViewSet)
router.register(r'', views.AlertViewSet)

urlpatterns = [
    url(r'^', include(router.urls)),
]
