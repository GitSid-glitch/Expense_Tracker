from django.urls import path

from core.views import dashboard_view

urlpatterns = [
    path("", dashboard_view, name="dashboard"),
]
