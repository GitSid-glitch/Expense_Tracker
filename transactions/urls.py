from django.urls import path

from transactions.views import (
    anomalies_view,
    category_create_view,
    category_delete_view,
    category_list_view,
    category_update_view,
    statement_import_view,
    transaction_bulk_upload_view,
    transaction_create_view,
    transaction_delete_view,
    transaction_list_view,
    transaction_update_view,
)

urlpatterns = [
    path("", transaction_list_view, name="transaction-list"),
    path("add/", transaction_create_view, name="transaction-add"),
    path("bulk-upload/", transaction_bulk_upload_view, name="transaction-bulk-upload"),
    path("import/", statement_import_view, name="statement-import"),
    path("anomalies/", anomalies_view, name="transaction-anomalies"),
    path("<int:pk>/edit/", transaction_update_view, name="transaction-edit"),
    path("<int:pk>/delete/", transaction_delete_view, name="transaction-delete"),
    path("categories/", category_list_view, name="category-list"),
    path("categories/add/", category_create_view, name="category-add"),
    path("categories/<int:pk>/edit/", category_update_view, name="category-edit"),
    path("categories/<int:pk>/delete/", category_delete_view, name="category-delete"),
]
