from django.urls import path

from budgets.views import (
    budget_create_view,
    budget_delete_view,
    budget_list_view,
    budget_update_view,
    notification_list_view,
    notification_mark_read_view,
)

urlpatterns = [
    path("", budget_list_view, name="budget-list"),
    path("add/", budget_create_view, name="budget-add"),
    path("<int:pk>/edit/", budget_update_view, name="budget-edit"),
    path("<int:pk>/delete/", budget_delete_view, name="budget-delete"),
    path("notifications/", notification_list_view, name="notification-list"),
    path("notifications/<int:pk>/read/", notification_mark_read_view, name="notification-read"),
]
