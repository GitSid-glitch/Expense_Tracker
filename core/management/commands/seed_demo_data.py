from datetime import timedelta
from decimal import Decimal
import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from budgets.models import Budget
from transactions.models import Category, Currency, Transaction, TransactionType


class Command(BaseCommand):
    help = "Seed demo finance data for local walkthroughs."

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            username="demo",
            defaults={
                "email": "demo@example.com",
                "first_name": "Demo",
                "last_name": "User",
            },
        )
        if created:
            user.set_password("demo12345")
            user.save()

        user.profile.preferred_currency = "INR"
        user.profile.save()

        inr = Currency.objects.get(code="INR")
        usd = Currency.objects.get(code="USD")

        categories = {
            "salary": Category.objects.get_or_create(user=user, name="Salary", transaction_type=TransactionType.INCOME)[0],
            "freelance": Category.objects.get_or_create(user=user, name="Freelance", transaction_type=TransactionType.INCOME)[0],
            "groceries": Category.objects.get_or_create(user=user, name="Groceries", transaction_type=TransactionType.EXPENSE)[0],
            "rent": Category.objects.get_or_create(user=user, name="Rent", transaction_type=TransactionType.EXPENSE)[0],
            "travel": Category.objects.get_or_create(user=user, name="Travel", transaction_type=TransactionType.EXPENSE)[0],
            "mutual_fund": Category.objects.get_or_create(user=user, name="Mutual Fund", transaction_type=TransactionType.INVESTMENT)[0],
        }

        today = timezone.localdate()
        for month_offset in range(0, 4):
            month_date = (today.replace(day=1) - timedelta(days=month_offset * 30)).replace(day=1)
            Budget.objects.get_or_create(
                user=user,
                category=categories["groceries"],
                month=month_date,
                defaults={"limit_amount": Decimal("12000.00")},
            )
            Budget.objects.get_or_create(
                user=user,
                category=categories["travel"],
                month=month_date,
                defaults={"limit_amount": Decimal("8000.00")},
            )

        if not Transaction.objects.filter(user=user).exists():
            for month_offset in range(0, 4):
                base_date = (today.replace(day=1) - timedelta(days=month_offset * 30)).replace(day=5)
                Transaction.objects.create(
                    user=user,
                    category=categories["salary"],
                    transaction_type=TransactionType.INCOME,
                    date=base_date,
                    amount=Decimal("85000.00"),
                    currency=inr,
                    description="Monthly salary",
                )
                Transaction.objects.create(
                    user=user,
                    category=categories["freelance"],
                    transaction_type=TransactionType.INCOME,
                    date=base_date + timedelta(days=9),
                    amount=Decimal("300.00"),
                    currency=usd,
                    description="Freelance client payment",
                )
                Transaction.objects.create(
                    user=user,
                    category=categories["rent"],
                    transaction_type=TransactionType.EXPENSE,
                    date=base_date + timedelta(days=1),
                    amount=Decimal("25000.00"),
                    currency=inr,
                    description="Monthly house rent",
                )
                Transaction.objects.create(
                    user=user,
                    category=categories["mutual_fund"],
                    transaction_type=TransactionType.INVESTMENT,
                    date=base_date + timedelta(days=2),
                    amount=Decimal("10000.00"),
                    currency=inr,
                    description="SIP contribution",
                )
                for day_shift in (3, 8, 14, 20):
                    Transaction.objects.create(
                        user=user,
                        category=random.choice([categories["groceries"], categories["travel"]]),
                        transaction_type=TransactionType.EXPENSE,
                        date=base_date + timedelta(days=day_shift),
                        amount=Decimal(str(random.choice([1200, 1800, 2400, 3500, 4200]))),
                        currency=inr,
                        description="Routine spending",
                    )

        self.stdout.write(self.style.SUCCESS("Demo data ready. Login with username 'demo' and password 'demo12345'."))
