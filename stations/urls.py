from django.conf.urls import url
from django.urls import include
from rest_framework.routers import SimpleRouter

from stations import views

router = SimpleRouter()
router.register(r"stations", views.StationViewSet)
router.register(r"sites", views.SiteViewSet)

urlpatterns = [
    url(r"^", include(router.urls)),
    url(r"^measurements/summary?", views.MeasurementSummaryView.as_view()),
]
