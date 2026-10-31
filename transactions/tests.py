from django.core.files.uploadedfile import SimpleUploadedFile
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from transactions.forms import CategoryForm, TransactionForm
from transactions.importers import bulk_import_transactions, import_statement
from transactions.models import Category, Currency, ImportedTransaction, StatementImport, Transaction, TransactionType
from transactions.services import convert_amount, detect_transaction_anomalies


class TransactionModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="bob", password="secret123")
        self.currency, _ = Currency.objects.get_or_create(
            code="INR",
            defaults={"name": "Indian Rupee", "symbol": "Rs"},
        )
        self.category = Category.objects.create(
            user=self.user,
            name="Food",
            transaction_type=TransactionType.EXPENSE,
        )

    def test_negative_expense_is_marked_as_refund(self):
        transaction = Transaction.objects.create(
            user=self.user,
            category=self.category,
            transaction_type=TransactionType.EXPENSE,
            date=date(2026, 4, 1),
            amount=Decimal("-150.00"),
            currency=self.currency,
            description="Restaurant refund",
        )
        self.assertTrue(transaction.is_refund)

    def test_negative_income_is_rejected(self):
        income_category = Category.objects.create(
            user=self.user,
            name="Salary",
            transaction_type=TransactionType.INCOME,
        )
        with self.assertRaises(ValidationError):
            Transaction.objects.create(
                user=self.user,
                category=income_category,
                transaction_type=TransactionType.INCOME,
                date=date(2026, 4, 3),
                amount=Decimal("-10.00"),
                currency=self.currency,
                description="Invalid negative income",
            )

    def test_category_snapshot_is_preserved_when_category_deleted(self):
        transaction = Transaction.objects.create(
            user=self.user,
            category=self.category,
            transaction_type=TransactionType.EXPENSE,
            date=date(2026, 4, 2),
            amount=Decimal("200.00"),
            currency=self.currency,
            description="Dinner",
        )
        self.category.delete()
        transaction.refresh_from_db()
        self.assertIsNone(transaction.category)
        self.assertEqual(transaction.category_snapshot, "Food")

    def test_zero_amount_is_rejected(self):
        with self.assertRaises(ValidationError):
            Transaction.objects.create(
                user=self.user,
                category=self.category,
                transaction_type=TransactionType.EXPENSE,
                date=date(2026, 4, 2),
                amount=Decimal("0.00"),
                currency=self.currency,
                description="Invalid transaction",
            )

    def test_currency_conversion_to_target_currency(self):
        usd, _ = Currency.objects.update_or_create(
            code="USD",
            defaults={
                "name": "US Dollar",
                "symbol": "$",
                "exchange_rate_to_inr": Decimal("80.0000"),
            },
        )
        converted = convert_amount(Decimal("160.00"), self.currency, usd)
        self.assertEqual(converted, Decimal("2.00"))

    def test_form_rejects_category_type_mismatch(self):
        income_category = Category.objects.create(
            user=self.user,
            name="Salary",
            transaction_type=TransactionType.INCOME,
        )
        form = TransactionForm(
            data={
                "transaction_type": TransactionType.EXPENSE,
                "category": income_category.pk,
                "date": "2026-04-10",
                "amount": "100.00",
                "currency": self.currency.pk,
                "description": "Mismatch",
                "notes": "",
            },
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)

    def test_form_accepts_category_owned_by_current_user(self):
        income_category = Category.objects.create(
            user=self.user,
            name="Salary",
            transaction_type=TransactionType.INCOME,
        )
        form = TransactionForm(
            data={
                "transaction_type": TransactionType.INCOME,
                "category": income_category.pk,
                "date": "2026-04-10",
                "amount": "50000.00",
                "currency": self.currency.pk,
                "description": "First credit of the month",
                "notes": "",
            },
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_accepts_valid_receipt_upload(self):
        receipt = SimpleUploadedFile(
            "receipt.pdf",
            b"%PDF-1.4 fake content",
            content_type="application/pdf",
        )
        form = TransactionForm(
            data={
                "transaction_type": TransactionType.EXPENSE,
                "category": self.category.pk,
                "date": "2026-04-10",
                "amount": "100.00",
                "currency": self.currency.pk,
                "description": "Receipt upload",
                "notes": "",
            },
            files={"receipt": receipt},
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejects_invalid_receipt_type(self):
        receipt = SimpleUploadedFile(
            "receipt.txt",
            b"plain text",
            content_type="text/plain",
        )
        form = TransactionForm(
            data={
                "transaction_type": TransactionType.EXPENSE,
                "category": self.category.pk,
                "date": "2026-04-10",
                "amount": "100.00",
                "currency": self.currency.pk,
                "description": "Bad receipt upload",
                "notes": "",
            },
            files={"receipt": receipt},
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("receipt", form.errors)

    def test_form_rejects_negative_non_expense_amount(self):
        income_category = Category.objects.create(
            user=self.user,
            name="Freelance",
            transaction_type=TransactionType.INCOME,
        )
        form = TransactionForm(
            data={
                "transaction_type": TransactionType.INCOME,
                "category": income_category.pk,
                "date": "2026-04-10",
                "amount": "-25.00",
                "currency": self.currency.pk,
                "description": "Invalid income",
                "notes": "",
            },
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("amount", form.errors)

    def test_duplicate_category_name_is_rejected_case_insensitively(self):
        form = CategoryForm(
            data={
                "name": "food",
                "transaction_type": TransactionType.EXPENSE,
                "is_active": True,
            },
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_statement_import_creates_transaction_and_detects_duplicates(self):
        csv_content = b"date,amount,description,currency\n2026-04-10,1200.00,Grocery Store,INR\n"
        statement = StatementImport.objects.create(
            user=self.user,
            source_name="April Import",
            file=SimpleUploadedFile("statement.csv", csv_content, content_type="text/csv"),
        )

        def currency_lookup(code):
            return Currency.objects.get(code=code)

        import_statement(statement, currency_lookup)
        statement.refresh_from_db()
        self.assertEqual(statement.imported_count, 1)
        self.assertEqual(ImportedTransaction.objects.count(), 1)

        duplicate_statement = StatementImport.objects.create(
            user=self.user,
            source_name="Duplicate Import",
            file=SimpleUploadedFile("statement.csv", csv_content, content_type="text/csv"),
        )
        import_statement(duplicate_statement, currency_lookup)
        duplicate_statement.refresh_from_db()
        self.assertEqual(duplicate_statement.duplicate_count, 1)

    def test_statement_import_accepts_explicit_type_and_skips_invalid_rows(self):
        csv_content = (
            b"date,amount,description,currency,transaction_type\n"
            b"2026-04-10,1200.00,Salary payout,INR,income\n"
            b"bad-date,50.00,Invalid date,INR,expense\n"
            b"2026-04-11,25.00,Unknown currency,XYZ,expense\n"
        )
        statement = StatementImport.objects.create(
            user=self.user,
            source_name="April Statement",
            file=SimpleUploadedFile("statement.csv", csv_content, content_type="text/csv"),
        )

        def currency_lookup(code):
            currency = Currency.objects.filter(code=code).first()
            if currency is None:
                raise ValidationError("Unsupported currency")
            return currency

        import_statement(statement, currency_lookup)
        statement.refresh_from_db()
        self.assertEqual(statement.imported_count, 1)
        self.assertEqual(statement.skipped_count, 2)
        imported = Transaction.objects.get(description="Salary payout")
        self.assertEqual(imported.transaction_type, TransactionType.INCOME)

    def test_bulk_import_creates_multiple_transactions(self):
        csv_content = (
            b"date,amount,description,currency,transaction_type,category,notes\n"
            b"2026-04-10,1200.00,Salary payout,INR,income,Salary,Monthly salary\n"
            b"2026-04-11,250.00,Uber ride,INR,expense,Travel,Cab fare\n"
            b"2026-04-12,500.00,ETF purchase,INR,investment,ETF,Portfolio contribution\n"
        )
        upload = StatementImport.objects.create(
            user=self.user,
            source_name="Bulk upload: April batch",
            file=SimpleUploadedFile("bulk.csv", csv_content, content_type="text/csv"),
        )

        def currency_lookup(code):
            return Currency.objects.get(code=code)

        bulk_import_transactions(upload, currency_lookup)
        upload.refresh_from_db()

        self.assertEqual(upload.imported_count, 3)
        self.assertEqual(
            Transaction.objects.filter(user=self.user, description__in=["Salary payout", "Uber ride", "ETF purchase"]).count(),
            3,
        )

    def test_transaction_list_supports_advanced_filters(self):
        self.client.login(username="bob", password="secret123")
        usd, _ = Currency.objects.update_or_create(
            code="USD",
            defaults={"name": "US Dollar", "symbol": "$", "exchange_rate_to_inr": Decimal("80.0000")},
        )
        Transaction.objects.create(
            user=self.user,
            category=self.category,
            transaction_type=TransactionType.EXPENSE,
            date=date(2026, 4, 10),
            amount=Decimal("125.00"),
            currency=usd,
            description="Dinner with team",
            notes="Business meal",
        )
        Transaction.objects.create(
            user=self.user,
            category=self.category,
            transaction_type=TransactionType.EXPENSE,
            date=date(2026, 4, 11),
            amount=Decimal("-50.00"),
            currency=self.currency,
            description="Refund from cafe",
        )

        response = self.client.get(
            reverse("transaction-list"),
            {
                "currency": "USD",
                "refund": "no",
                "amount_min": "100",
                "search": "team",
                "category": str(self.category.pk),
            },
        )

        self.assertEqual(response.status_code, 200)
        transactions = list(response.context["transactions"])
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0].description, "Dinner with team")

    def test_anomaly_detection_flags_large_expense(self):
        for amount in ("100.00", "120.00", "140.00", "900.00"):
            Transaction.objects.create(
                user=self.user,
                category=self.category,
                transaction_type=TransactionType.EXPENSE,
                date=date(2026, 4, 12),
                amount=Decimal(amount),
                currency=self.currency,
                description=f"Expense {amount}",
            )
        anomalies = detect_transaction_anomalies(Transaction.objects.for_user(self.user))
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["transaction"].description, "Expense 900.00")
        self.assertEqual(anomalies[0]["baseline_scope"], "Food category history")

    def test_anomaly_detection_ignores_refunds(self):
        for amount in ("100.00", "110.00", "115.00", "-600.00"):
            Transaction.objects.create(
                user=self.user,
                category=self.category,
                transaction_type=TransactionType.EXPENSE,
                date=date(2026, 4, 12),
                amount=Decimal(amount),
                currency=self.currency,
                description=f"Expense {amount}",
            )
        anomalies = detect_transaction_anomalies(Transaction.objects.for_user(self.user))
        self.assertEqual(len(anomalies), 0)

    def test_anomaly_detection_uses_global_baseline_when_category_history_is_small(self):
        travel_category = Category.objects.create(
            user=self.user,
            name="Travel",
            transaction_type=TransactionType.EXPENSE,
        )
        for amount in ("100.00", "105.00", "110.00", "115.00", "120.00"):
            Transaction.objects.create(
                user=self.user,
                category=self.category,
                transaction_type=TransactionType.EXPENSE,
                date=date(2026, 4, 12),
                amount=Decimal(amount),
                currency=self.currency,
                description=f"Food {amount}",
            )
        Transaction.objects.create(
            user=self.user,
            category=travel_category,
            transaction_type=TransactionType.EXPENSE,
            date=date(2026, 4, 13),
            amount=Decimal("1000.00"),
            currency=self.currency,
            description="Flight booking",
        )

        anomalies = detect_transaction_anomalies(Transaction.objects.for_user(self.user))

        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["transaction"].description, "Flight booking")
        self.assertEqual(anomalies[0]["baseline_scope"], "overall expense history")

    def test_statement_import_view_requires_login(self):
        response = self.client.get(reverse("statement-import"))
        self.assertEqual(response.status_code, 302)
