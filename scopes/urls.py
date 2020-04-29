from django.conf.urls import url
from django.urls import include
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register(r'', views.ScopeViewSet)

urlpatterns = [
    url(r'^coverage/?', views.TimeSeries.as_view()),
    url(r'^available-dates/?', views.AvailableDates.as_view()),
    url(r'^types/?', views.ScopeTypes.as_view()),
    url(r'^', include(router.urls)),
]
