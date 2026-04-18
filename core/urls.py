from django.urls import path

from core.views import dashboard_view, health_view

urlpatterns = [
    path("health/", health_view, name="health"),
    path("", dashboard_view, name="dashboard"),
]
