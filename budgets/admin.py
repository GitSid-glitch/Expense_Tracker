from django.contrib import admin

from budgets.models import Budget, BudgetAlert, UserNotification


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ("user", "category", "month", "limit_amount", "spent_amount", "is_over_budget")
    search_fields = ("user__username", "category__name")
    list_filter = ("month",)


@admin.register(BudgetAlert)
class BudgetAlertAdmin(admin.ModelAdmin):
    list_display = ("budget", "threshold", "spent_amount", "created_at")
    search_fields = ("budget__user__username", "budget__category__name")


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "is_read", "created_at")
    search_fields = ("user__username", "title", "message")
    list_filter = ("is_read",)
