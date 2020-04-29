from django.conf.urls import url
from django.urls import include

from . import views

urlpatterns = [
    url(r'^coverage/?', views.TimeSeries.as_view()),
    url(r'^available-periods/?', views.AvailablePeriods.as_view()),
]
