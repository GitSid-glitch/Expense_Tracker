from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from budgets.models import Budget
from transactions.models import Category, Currency, Transaction, TransactionType


class DashboardViewTests(TestCase):
    def test_health_endpoint_returns_ok(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_health_endpoint_reports_database_failure(self):
        with patch("core.views.connection.cursor", side_effect=DatabaseError("database unavailable")):
            response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_renders_for_authenticated_user(self):
        user = User.objects.create_user(username="eve", password="secret123")
        self.client.login(username="eve", password="secret123")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")

    def test_dashboard_defaults_to_current_month_summary(self):
        user = User.objects.create_user(username="eve", password="secret123")
        currency, _ = Currency.objects.get_or_create(code="INR", defaults={"name": "Indian Rupee"})
        expense_category = Category.objects.create(
            user=user,
            name="Food",
            transaction_type=TransactionType.EXPENSE,
        )
        today = timezone.localdate()
        Transaction.objects.create(
            user=user,
            category=expense_category,
            transaction_type=TransactionType.EXPENSE,
            date=date(today.year, today.month, 5),
            amount=Decimal("125.00"),
            currency=currency,
            description="Current month expense",
        )
        Transaction.objects.create(
            user=user,
            category=expense_category,
            transaction_type=TransactionType.EXPENSE,
            date=date(today.year if today.month != 1 else today.year - 1, 1 if today.month != 1 else 12, 5),
            amount=Decimal("999.00"),
            currency=currency,
            description="Older expense",
        )
        self.client.login(username="eve", password="secret123")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["expense_total"], Decimal("125.00"))

    def test_dashboard_can_filter_by_year(self):
        user = User.objects.create_user(username="eve", password="secret123")
        currency, _ = Currency.objects.get_or_create(code="INR", defaults={"name": "Indian Rupee"})
        expense_category = Category.objects.create(
            user=user,
            name="Travel",
            transaction_type=TransactionType.EXPENSE,
        )
        Budget.objects.create(
            user=user,
            category=expense_category,
            month=date(2026, 1, 1),
            limit_amount=Decimal("1000.00"),
        )
        Transaction.objects.create(
            user=user,
            category=expense_category,
            transaction_type=TransactionType.EXPENSE,
            date=date(2026, 1, 10),
            amount=Decimal("250.00"),
            currency=currency,
            description="January travel",
        )
        self.client.login(username="eve", password="secret123")
        response = self.client.get(reverse("dashboard"), {"period": "year", "year": 2026})
        self.assertEqual(response.context["expense_total"], Decimal("250.00"))
        self.assertEqual(response.context["current_month_label"], "2026")
        self.assertEqual(len(response.context["active_budgets"]), 1)
