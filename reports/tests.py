from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from transactions.models import Category, Currency, Transaction, TransactionType


class ReportViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dana", password="secret123")
        self.client.login(username="dana", password="secret123")
        self.user.profile.preferred_currency = "USD"
        self.user.profile.save()
        self.inr, _ = Currency.objects.get_or_create(
            code="INR",
            defaults={"name": "Indian Rupee", "symbol": "Rs"},
        )
        self.usd, _ = Currency.objects.get_or_create(
            code="USD",
            defaults={"name": "US Dollar", "symbol": "$", "exchange_rate_to_inr": Decimal("80.0000")},
        )
        self.usd.exchange_rate_to_inr = Decimal("80.0000")
        self.usd.save(update_fields=["exchange_rate_to_inr"])
        self.category = Category.objects.create(
            user=self.user,
            name="Salary",
            transaction_type=TransactionType.INCOME,
        )
        Transaction.objects.create(
            user=self.user,
            category=self.category,
            transaction_type=TransactionType.INCOME,
            date=date(2026, 4, 1),
            amount=Decimal("8000.00"),
            currency=self.inr,
            description="Salary",
        )
        expense_category = Category.objects.create(
            user=self.user,
            name="Food",
            transaction_type=TransactionType.EXPENSE,
        )
        Transaction.objects.create(
            user=self.user,
            category=expense_category,
            transaction_type=TransactionType.EXPENSE,
            date=date(2026, 4, 4),
            amount=Decimal("1600.00"),
            currency=self.inr,
            description="Dining",
        )

    def test_monthly_report_renders_in_preferred_currency(self):
        response = self.client.get(reverse("monthly-report"), {"year": 2026, "month": 4})
        self.assertContains(response, "USD")
        self.assertContains(response, "100.00")

    def test_finance_summary_api_returns_expected_shape(self):
        response = self.client.get(reverse("api-finance-summary"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["currency"], "USD")

    def test_monthly_breakdown_api_requires_authentication(self):
        self.client.logout()
        response = self.client.get(reverse("api-monthly-breakdown"))
        self.assertEqual(response.status_code, 403)

    def test_monthly_report_csv_export(self):
        response = self.client.get(reverse("monthly-report"), {"export": "csv"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("monthly-report.csv", response["Content-Disposition"])

    def test_monthly_report_shows_category_summary(self):
        response = self.client.get(reverse("monthly-report"), {"year": 2026, "month": 4})
        self.assertContains(response, "Expense Category Summary")
        self.assertContains(response, "Food")

    def test_monthly_report_can_filter_by_year(self):
        Transaction.objects.create(
            user=self.user,
            category=self.category,
            transaction_type=TransactionType.INCOME,
            date=date(2025, 12, 1),
            amount=Decimal("4000.00"),
            currency=self.inr,
            description="Old salary",
        )
        response = self.client.get(reverse("monthly-report"), {"period": "year", "year": 2026})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2026")
        self.assertNotContains(response, "2025-12")
