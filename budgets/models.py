from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.functional import cached_property

from core.models import TimestampedModel
from transactions.models import Category, Currency, Transaction, TransactionType
from transactions.services import convert_amount


def default_budget_currency():
    return Currency.objects.get(code="INR").pk


class Budget(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="budgets")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="budgets")
    month = models.DateField(help_text="Use the first day of the month.")
    limit_amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, default=default_budget_currency)

    class Meta:
        ordering = ("-month", "category__name")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "category", "month"),
                name="unique_budget_per_category_month",
            )
        ]

    def clean(self):
        if self.limit_amount is not None and self.limit_amount <= Decimal("0.00"):
            raise ValidationError({"limit_amount": "Budget limit must be greater than zero."})
        if self.category.user_id != self.user_id:
            raise ValidationError("Budget category must belong to the same user.")
        if self.category.transaction_type != TransactionType.EXPENSE:
            raise ValidationError("Budgets can only be created for expense categories.")

    @cached_property
    def spent_amount(self):
        expenses = Transaction.objects.filter(
            user=self.user,
            category=self.category,
            transaction_type=TransactionType.EXPENSE,
            date__year=self.month.year,
            date__month=self.month.month,
        ).select_related("currency")
        return sum(
            (convert_amount(transaction.amount, transaction.currency, self.currency) for transaction in expenses),
            Decimal("0.00"),
        )

    @property
    def usage_percentage(self):
        if not self.limit_amount:
            return Decimal("0.00")
        return (self.spent_amount / self.limit_amount) * Decimal("100")

    @property
    def is_over_budget(self):
        return self.spent_amount > self.limit_amount

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.category.name} - {self.month:%Y-%m}"


class BudgetAlert(TimestampedModel):
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="alerts")
    threshold = models.PositiveSmallIntegerField()
    spent_amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("budget", "threshold"),
                name="unique_budget_threshold_alert",
            )
        ]

    def __str__(self):
        return f"{self.budget} - {self.threshold}%"


class UserNotification(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=150)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    related_budget_alert = models.OneToOneField(
        BudgetAlert,
        on_delete=models.CASCADE,
        related_name="notification",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("is_read", "-created_at")

    def __str__(self):
        return f"{self.user.username} - {self.title}"
