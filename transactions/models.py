from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimestampedModel


class TransactionType(models.TextChoices):
    INCOME = "income", "Income"
    EXPENSE = "expense", "Expense"
    INVESTMENT = "investment", "Investment"


class Currency(TimestampedModel):
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=5, blank=True)
    exchange_rate_to_inr = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("1.0000"))
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)

    def __str__(self):
        return self.code


class Category(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=100)
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("transaction_type", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "name", "transaction_type"),
                name="unique_category_per_user_and_type",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.transaction_type})"


class TransactionQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(user=user)

    def incomes(self):
        return self.filter(transaction_type=TransactionType.INCOME)

    def expenses(self):
        return self.filter(transaction_type=TransactionType.EXPENSE)

    def investments(self):
        return self.filter(transaction_type=TransactionType.INVESTMENT)


def receipt_upload_path(instance, filename):
    return f"receipts/user_{instance.user_id}/{filename}"


class Transaction(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions")
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name="transactions",
        blank=True,
        null=True,
    )
    category_snapshot = models.CharField(max_length=100, blank=True)
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="transactions")
    description = models.CharField(max_length=255)
    receipt = models.FileField(upload_to=receipt_upload_path, blank=True, null=True)
    notes = models.TextField(blank=True)
    is_refund = models.BooleanField(default=False)

    objects = TransactionQuerySet.as_manager()

    class Meta:
        ordering = ("-date", "-created_at")
        constraints = [models.CheckConstraint(condition=~Q(amount=0), name="transaction_amount_non_zero")]

    def clean(self):
        if self.amount is not None and self.transaction_type != TransactionType.EXPENSE and self.amount < 0:
            raise ValidationError({"amount": "Negative amounts are only allowed for expense refunds."})
        if self.category and self.category.user_id != self.user_id:
            raise ValidationError("Selected category does not belong to the current user.")
        if self.category and self.category.transaction_type != self.transaction_type:
            raise ValidationError("Category type must match transaction type.")

    def save(self, *args, **kwargs):
        if self.category:
            self.category_snapshot = self.category.name
        elif not self.category_snapshot:
            self.category_snapshot = "Uncategorized"
        self.is_refund = self.transaction_type == TransactionType.EXPENSE and self.amount < 0
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def display_category(self):
        return self.category.name if self.category else self.category_snapshot

    @property
    def amount_in_inr(self):
        return self.amount * self.currency.exchange_rate_to_inr

    def __str__(self):
        return f"{self.user} - {self.transaction_type} - {self.amount}"


def statement_upload_path(instance, filename):
    return f"statements/user_{instance.user_id}/{filename}"


class StatementImport(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="statement_imports")
    file = models.FileField(upload_to=statement_upload_path)
    source_name = models.CharField(max_length=255, blank=True)
    imported_count = models.PositiveIntegerField(default=0)
    duplicate_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.source_name or self.file.name


class ImportedTransaction(TimestampedModel):
    statement_import = models.ForeignKey(
        StatementImport,
        on_delete=models.CASCADE,
        related_name="imported_transactions",
    )
    transaction = models.OneToOneField(
        Transaction,
        on_delete=models.CASCADE,
        related_name="import_record",
    )
    fingerprint = models.CharField(max_length=64)
    raw_description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("statement_import", "fingerprint"),
                name="unique_import_fingerprint_per_statement",
            )
        ]
