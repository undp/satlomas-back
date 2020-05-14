from django.conf.urls import url
from django.urls import include
from rest_framework.routers import SimpleRouter

from alerts import views

router = SimpleRouter()
router.register(r'parameter-rules', views.ParameterRuleViewSet)
router.register(r'scope-rules', views.ScopeRuleViewSet)
router.register(r'scope-type-rules', views.ScopeTypeRuleViewSet)
router.register(r'user-profiles', views.UserProfileViewSet)
router.register(r'users', views.UserViewSet)
router.register(r'', views.AlertViewSet)

urlpatterns = [
    url(r'^latest', views.LatestAlerts.as_view()),
    url(r'^seen', views.SeenAlerts.as_view()),
    url(r'^', include(router.urls)),
]
