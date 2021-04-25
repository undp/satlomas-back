from django.conf.urls import url
from django.urls import include
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register(r"rasters", views.RasterViewSet)

urlpatterns = [
    url(r"^", include(router.urls)),
    url(r"^download-raster/(?P<pk>[^/]+)$", views.RasterDownloadView.as_view()),
    url(r"^coverage/?", views.CoverageView.as_view()),
    url(r"^available-dates/?", views.AvailableDatesView.as_view()),
    url(r"^import/sftp/list/?", views.ImportSFTPListView.as_view()),
    url(r"^import/sftp/?", views.ImportSFTPView.as_view()),
]
