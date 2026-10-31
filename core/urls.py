from django.urls import path

from core.views import dashboard_view, health_view, load_sample_data_view

urlpatterns = [
    path("health/", health_view, name="health"),
    path("sample-data/", load_sample_data_view, name="load-sample-data"),
    path("", dashboard_view, name="dashboard"),
]
