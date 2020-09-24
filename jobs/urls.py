from django.conf.urls import url
from django.urls import include
from rest_framework.routers import SimpleRouter

from jobs import views

router = SimpleRouter()
router.register(r'', views.JobViewSet)

urlpatterns = [
    url(r'^', include(router.urls)),
]
