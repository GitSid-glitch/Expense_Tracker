from django.contrib import admin

from transactions.models import Category, Currency, ImportedTransaction, StatementImport, Transaction


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "exchange_rate_to_inr", "is_active")
    search_fields = ("code", "name")
    list_filter = ("is_active",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "transaction_type", "user", "is_active")
    search_fields = ("name", "user__username")
    list_filter = ("transaction_type", "is_active")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "transaction_type", "amount", "currency", "date", "display_category")
    search_fields = ("description", "user__username", "category_snapshot")
    list_filter = ("transaction_type", "currency__code", "date")


@admin.register(StatementImport)
class StatementImportAdmin(admin.ModelAdmin):
    list_display = ("user", "source_name", "imported_count", "duplicate_count", "skipped_count", "created_at")
    search_fields = ("user__username", "source_name")


@admin.register(ImportedTransaction)
class ImportedTransactionAdmin(admin.ModelAdmin):
    list_display = ("statement_import", "transaction", "created_at")
    search_fields = ("raw_description", "transaction__description")
