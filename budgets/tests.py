from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase

from budgets.forms import BudgetForm
from budgets.models import Budget, UserNotification
from budgets.services import send_budget_alerts_for_budget
from transactions.models import Category, Currency, Transaction, TransactionType


class BudgetModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cara", password="secret123")
        self.currency, _ = Currency.objects.get_or_create(
            code="INR",
            defaults={"name": "Indian Rupee", "symbol": "Rs"},
        )
        self.category = Category.objects.create(
            user=self.user,
            name="Groceries",
            transaction_type=TransactionType.EXPENSE,
        )

    def test_spent_amount_and_over_budget(self):
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            month=date(2026, 4, 1),
            limit_amount=Decimal("500.00"),
        )
        Transaction.objects.create(
            user=self.user,
            category=self.category,
            transaction_type=TransactionType.EXPENSE,
            date=date(2026, 4, 10),
            amount=Decimal("600.00"),
            currency=self.currency,
            description="Monthly grocery shopping",
        )
        self.assertEqual(budget.spent_amount, Decimal("600.00"))
        self.assertTrue(budget.is_over_budget)

    def test_budget_alert_email_sent_once_per_threshold(self):
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            month=date(2026, 4, 1),
            limit_amount=Decimal("500.00"),
        )
        Transaction.objects.create(
            user=self.user,
            category=self.category,
            transaction_type=TransactionType.EXPENSE,
            date=date(2026, 4, 10),
            amount=Decimal("450.00"),
            currency=self.currency,
            description="Groceries",
        )
        triggered = send_budget_alerts_for_budget(budget)
        self.assertEqual(triggered, [80])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(UserNotification.objects.filter(user=self.user).count(), 1)
        triggered_again = send_budget_alerts_for_budget(budget)
        self.assertEqual(triggered_again, [])

    def test_notification_marked_read(self):
        notification = UserNotification.objects.create(
            user=self.user,
            title="Budget alert",
            message="Test notification",
        )
        self.client.login(username="cara", password="secret123")
        response = self.client.post(f"/budgets/notifications/{notification.pk}/read/")
        self.assertEqual(response.status_code, 302)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_notification_list_marks_unread_notifications_as_read(self):
        first = UserNotification.objects.create(
            user=self.user,
            title="Budget alert",
            message="First notification",
        )
        second = UserNotification.objects.create(
            user=self.user,
            title="Budget alert",
            message="Second notification",
        )
        self.client.login(username="cara", password="secret123")

        response = self.client.get("/budgets/notifications/")

        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertTrue(first.is_read)
        self.assertTrue(second.is_read)
        self.assertContains(response, "0 unread")

    def test_form_accepts_category_owned_by_current_user(self):
        form = BudgetForm(
            data={
                "category": self.category.pk,
                "month": "2026-04",
                "limit_amount": "1000.00",
            },
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejects_duplicate_budget_in_same_month(self):
        Budget.objects.create(
            user=self.user,
            category=self.category,
            month=date(2026, 4, 1),
            limit_amount=Decimal("500.00"),
        )
        form = BudgetForm(
            data={
                "category": self.category.pk,
                "month": "2026-04",
                "limit_amount": "600.00",
            },
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)

    def test_form_rejects_non_positive_limit(self):
        form = BudgetForm(
            data={
                "category": self.category.pk,
                "month": "2026-04",
                "limit_amount": "0.00",
            },
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("limit_amount", form.errors)

    def test_creating_budget_after_existing_expenses_generates_notification(self):
        self.client.login(username="cara", password="secret123")
        Transaction.objects.create(
            user=self.user,
            category=self.category,
            transaction_type=TransactionType.EXPENSE,
            date=date(2026, 4, 10),
            amount=Decimal("900.00"),
            currency=self.currency,
            description="Large grocery spend",
        )

        response = self.client.post(
            "/budgets/add/",
            data={
                "category": self.category.pk,
                "month": "2026-04",
                "limit_amount": "1000.00",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(UserNotification.objects.filter(user=self.user).count(), 1)
