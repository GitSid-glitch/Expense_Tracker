import csv
import io
from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from accounts.models import Profile
from budgets.models import Budget, BudgetAlert, UserNotification
from transactions.importers import bulk_import_transactions, import_statement
from transactions.models import Category, Currency, StatementImport, Transaction, TransactionType


SAMPLE_NOTE = "Sample data: added by Moneta's interactive walkthrough."


def _month_date(today, months_ago, day):
    month_index = today.year * 12 + today.month - 1 - months_ago
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    last_day = monthrange(year, month)[1]
    safe_day = min(day, last_day)
    if months_ago == 0:
        safe_day = min(safe_day, today.day)
    return date(year, month, safe_day)


def _csv_file(headers, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return ContentFile(buffer.getvalue().encode("utf-8"))


def _sample_pdf(lines):
    pdf_lines = ["BT /F1 11 Tf 48 740 Td 15 TL"]
    for line in lines:
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        pdf_lines.append(f"({escaped}) Tj T*")
    pdf_lines.append("ET")
    stream = "\n".join(pdf_lines).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    document = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(document))
        document.extend(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref_offset = len(document)
    document.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    document.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(document)


def _currency_lookup(code):
    return Currency.objects.get(code=code, is_active=True)


def sample_workspace_available(user):
    profile = user.profile
    if profile.sample_data_loaded:
        return False
    return not any(
        queryset.exists()
        for queryset in (
            Transaction.objects.filter(user=user),
            Category.objects.filter(user=user),
            Budget.objects.filter(user=user),
            StatementImport.objects.filter(user=user),
            UserNotification.objects.filter(user=user),
        )
    )


@transaction.atomic
def load_sample_workspace(user):
    """Populate an empty account with a deterministic, feature-rich walkthrough."""
    profile = Profile.objects.select_for_update().get(user=user)
    if profile.sample_data_loaded or any(
        queryset.exists()
        for queryset in (
            Transaction.objects.filter(user=user),
            Category.objects.filter(user=user),
            Budget.objects.filter(user=user),
            StatementImport.objects.filter(user=user),
            UserNotification.objects.filter(user=user),
        )
    ):
        return False

    today = timezone.localdate()
    currencies = {
        code: Currency.objects.get(code=code, is_active=True)
        for code in ("INR", "USD", "EUR", "GBP", "AED")
    }
    categories = {}
    category_specs = {
        "salary": ("Salary", TransactionType.INCOME),
        "freelance": ("Freelance", TransactionType.INCOME),
        "groceries": ("Groceries", TransactionType.EXPENSE),
        "rent": ("Rent", TransactionType.EXPENSE),
        "dining": ("Dining", TransactionType.EXPENSE),
        "transport": ("Transport", TransactionType.EXPENSE),
        "utilities": ("Utilities", TransactionType.EXPENSE),
        "subscriptions": ("Subscriptions", TransactionType.EXPENSE),
        "travel": ("Travel", TransactionType.EXPENSE),
        "investments": ("Index fund", TransactionType.INVESTMENT),
    }
    for key, (name, transaction_type) in category_specs.items():
        categories[key], _ = Category.objects.get_or_create(
            user=user,
            name=name,
            transaction_type=transaction_type,
            defaults={"is_active": True},
        )
    Category.objects.get_or_create(
        user=user,
        name="Archived category",
        transaction_type=TransactionType.EXPENSE,
        defaults={"is_active": False},
    )

    def add_transaction(key, amount, currency_code, description, day, months_ago, notes=SAMPLE_NOTE):
        return Transaction.objects.create(
            user=user,
            category=categories[key],
            transaction_type=categories[key].transaction_type,
            date=_month_date(today, months_ago, day),
            amount=Decimal(str(amount)),
            currency=currencies[currency_code],
            description=description,
            notes=notes,
        )

    # Six months of repeatable activity makes the dashboard, filters and reports useful.
    for months_ago in reversed(range(6)):
        add_transaction("salary", "85000.00", "INR", "Monthly salary", 1, months_ago)
        add_transaction("rent", "25000.00", "INR", "Apartment rent", 3, months_ago)
        add_transaction("utilities", "2450.00", "INR", "Electricity and internet", 5, months_ago)
        add_transaction("subscriptions", "799.00", "INR", "Streaming subscription", 7, months_ago)
        for day, amount in ((9, "950.00"), (13, "1450.00"), (18, "2100.00"), (23, "1650.00")):
            add_transaction("groceries", amount, "INR", "Weekly grocery shop", day, months_ago)
        add_transaction("dining", "1250.00", "INR", "Dinner with friends", 11, months_ago)
        add_transaction("dining", "680.00", "INR", "Cafe lunch", 21, months_ago)
        add_transaction("transport", "540.00", "INR", "Metro and rideshare", 15, months_ago)
        add_transaction("investments", "10000.00", "INR", "Monthly index fund SIP", 25, months_ago)
        if months_ago % 2 == 0:
            add_transaction("freelance", "240.00", "USD", "Design project payment", 19, months_ago)
            add_transaction("travel", "6800.00", "INR", "Weekend train trip", 27, months_ago)

    # One clearly labeled high grocery charge exercises the anomaly and over-budget flows.
    add_transaction("groceries", "18500.00", "INR", "Unusually large grocery purchase", 26, 0)
    add_transaction("groceries", "-650.00", "INR", "Returned grocery item", 28, 0)
    add_transaction("travel", "78.00", "EUR", "Airport transfer abroad", 16, 1)
    add_transaction("transport", "35.00", "AED", "Taxi fare abroad", 18, 2)
    add_transaction("travel", "52.00", "GBP", "Hotel deposit abroad", 20, 3)

    # The CSV import screens show both imported rows and duplicate / invalid row handling.
    statement_rows = [
        (_month_date(today, 0, 8).isoformat(), "620.00", "Sample statement cafe", "INR", "expense"),
        (_month_date(today, 0, 10).isoformat(), "1850.00", "Sample statement pharmacy", "INR", "expense"),
        (_month_date(today, 0, 8).isoformat(), "620.00", "Sample statement cafe", "INR", "expense"),
        ("not-a-date", "900.00", "Sample statement skipped row", "INR", "expense"),
    ]
    statement = StatementImport(user=user, source_name="Sample bank statement · CSV walkthrough")
    statement.file.save(
        "sample-bank-statement.csv",
        _csv_file(("date", "amount", "description", "currency", "transaction_type"), statement_rows),
        save=True,
    )
    import_statement(statement, _currency_lookup)

    bulk_rows = [
        (_month_date(today, 0, 12).isoformat(), "320.00", "Sample bulk purchase", "INR", "expense", "Groceries", "Demo CSV row"),
        (_month_date(today, 0, 14).isoformat(), "125.00", "Sample bulk refund", "INR", "expense", "Groceries", "Demo refund row"),
        ("invalid-date", "500.00", "Sample invalid row", "INR", "expense", "Dining", "Skipped on import"),
    ]
    bulk_upload = StatementImport(user=user, source_name="Bulk upload: sample-transactions.csv")
    bulk_upload.file.save(
        "sample-transactions.csv",
        _csv_file(
            ("date", "amount", "description", "currency", "transaction_type", "category", "notes"),
            bulk_rows,
        ),
        save=True,
    )
    bulk_import_transactions(bulk_upload, _currency_lookup)

    pdf_rows = [
        "date,amount,description,currency",
        f"{_month_date(today, 0, 17).isoformat()},480.00,Sample PDF bookstore,INR",
        f"{_month_date(today, 0, 19).isoformat()},960.00,Sample PDF household supplies,INR",
    ]
    pdf_bytes = _sample_pdf(pdf_rows)
    pdf_statement = StatementImport(user=user, source_name="Sample PDF statement · walkthrough")
    pdf_statement.file.save("sample-card-statement.pdf", ContentFile(pdf_bytes), save=True)
    import_statement(pdf_statement, _currency_lookup)

    receipt_transaction = Transaction.objects.filter(
        user=user,
        description="Dinner with friends",
        notes=SAMPLE_NOTE,
    ).order_by("-date").first()
    if receipt_transaction:
        receipt_transaction.receipt.save(
            "sample-receipt.pdf",
            ContentFile(
                _sample_pdf(
                    [
                        "MONETA SAMPLE RECEIPT",
                        "Dinner with friends",
                        f"Date: {_month_date(today, 0, 11).isoformat()}",
                        "Amount: INR 1250.00",
                        "Paid by card",
                    ]
                ),
            ),
            save=True,
        )

    for months_ago in reversed(range(6)):
        month = _month_date(today, months_ago, 1)
        for key, limit in (
            ("groceries", "12000.00"),
            ("rent", "30000.00"),
            ("dining", "6500.00"),
            ("travel", "10000.00"),
        ):
            Budget.objects.get_or_create(
                user=user,
                category=categories[key],
                month=month,
                defaults={"limit_amount": Decimal(limit), "currency": currencies["INR"]},
            )

    grocery_budget = Budget.objects.get(user=user, category=categories["groceries"], month=_month_date(today, 0, 1))
    spent = grocery_budget.spent_amount
    for threshold in (80, 100):
        alert, _ = BudgetAlert.objects.get_or_create(
            budget=grocery_budget,
            threshold=threshold,
            defaults={"spent_amount": spent},
        )
        UserNotification.objects.get_or_create(
            related_budget_alert=alert,
            defaults={
                "user": user,
                "title": f"Budget alert for {grocery_budget.category.name}",
                "message": (
                    f"Your sample Groceries budget has reached {threshold}% usage. "
                    f"Spent: {spent} INR. Limit: {grocery_budget.limit_amount} INR."
                ),
                "is_read": threshold == 80,
            },
        )

    profile.sample_data_loaded = True
    profile.save(update_fields=["sample_data_loaded", "updated_at"])
    return True
