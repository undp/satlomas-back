from django.conf.urls import url
from django.urls import include
from rest_framework.routers import SimpleRouter

from stations import views

router = SimpleRouter()
router.register(r'places', views.PlaceViewSet)
router.register(r'stations', views.StationViewSet)

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^measurements/summary?', views.MeasurementSummaryView.as_view()),
]
