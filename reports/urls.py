from django.urls import path

from reports.api import finance_summary_api, monthly_breakdown_api
from reports.views import monthly_report_view

urlpatterns = [
    path("monthly/", monthly_report_view, name="monthly-report"),
    path("api/summary/", finance_summary_api, name="api-finance-summary"),
    path("api/monthly-breakdown/", monthly_breakdown_api, name="api-monthly-breakdown"),
]
