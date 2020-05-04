from django.conf.urls import url
from django.urls import include
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register(r'rasters', views.RasterViewSet)

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^coverage/?', views.TimeSeries.as_view()),
    url(r'^available-periods/?', views.AvailablePeriods.as_view()),
]
