import csv
import hashlib
import io
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from transactions.models import Category, ImportedTransaction, Transaction, TransactionType


def fingerprint_row(date_value, amount_value, description_value, currency_code):
    raw = f"{date_value}|{amount_value}|{description_value.strip().lower()}|{currency_code}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def infer_transaction_type(amount):
    return TransactionType.EXPENSE if amount >= 0 else TransactionType.INCOME


def get_default_category(user, transaction_type):
    category_name = "Imported Income" if transaction_type == TransactionType.INCOME else "Imported Expense"
    category, _ = Category.objects.get_or_create(
        user=user,
        name=category_name,
        transaction_type=transaction_type,
        defaults={"is_active": True},
    )
    return category


def categorize_from_description(user, transaction_type, description):
    lowered = description.lower()
    mapping = {
        "salary": "Salary",
        "rent": "Rent",
        "grocery": "Groceries",
        "food": "Food",
        "restaurant": "Food",
        "travel": "Travel",
        "uber": "Travel",
        "flight": "Travel",
        "sip": "Mutual Fund",
        "investment": "Mutual Fund",
    }
    for keyword, category_name in mapping.items():
        if keyword in lowered:
            category, _ = Category.objects.get_or_create(
                user=user,
                name=category_name,
                transaction_type=transaction_type,
                defaults={"is_active": True},
            )
            return category
    return get_default_category(user, transaction_type)


def parse_csv_rows(file_obj):
    try:
        decoded = file_obj.read().decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValidationError("Statement CSV must be UTF-8 encoded.") from error
    reader = csv.DictReader(io.StringIO(decoded))
    for row in reader:
        yield {
            "date": row.get("date") or row.get("Date"),
            "amount": row.get("amount") or row.get("Amount"),
            "description": row.get("description") or row.get("Description") or "",
            "currency": row.get("currency") or row.get("Currency") or "INR",
            "transaction_type": row.get("transaction_type") or row.get("Transaction Type") or "",
        }


def parse_pdf_rows(file_obj):
    try:
        reader = PdfReader(file_obj)
    except PdfReadError as error:
        raise ValidationError("Statement PDF could not be read.") from error
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    rows = []
    for line in text.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 4:
            rows.append(
                {
                    "date": parts[0],
                    "amount": parts[1],
                    "description": parts[2],
                    "currency": parts[3] or "INR",
                }
            )
    return rows


@db_transaction.atomic
def import_statement(statement_import, currency_lookup):
    uploaded_file = statement_import.file
    uploaded_file.open("rb")
    filename = uploaded_file.name.lower()

    if filename.endswith(".csv"):
        rows = list(parse_csv_rows(uploaded_file))
    elif filename.endswith(".pdf"):
        rows = parse_pdf_rows(uploaded_file)
    else:
        raise ValidationError("Upload a CSV or PDF statement.")

    if not rows:
        raise ValidationError("No transaction rows were found in this statement.")

    for row in rows:
        try:
            amount_value = Decimal(str(row["amount"]).replace(",", ""))
            if not amount_value.is_finite() or amount_value == 0:
                raise ValidationError("Amount must be a finite non-zero number.")
            date_value = date.fromisoformat(str(row.get("date") or ""))
            transaction_type = _normalize_transaction_type(row.get("transaction_type"), amount_value)
            description_value = (row.get("description") or "Imported transaction").strip()
            currency_code = (row.get("currency") or "INR").strip().upper()
            currency = currency_lookup(currency_code)
        except (InvalidOperation, TypeError, ValueError, ValidationError):
            statement_import.skipped_count += 1
            continue

        fingerprint = fingerprint_row(date_value, amount_value, description_value, currency_code)

        if ImportedTransaction.objects.filter(transaction__user=statement_import.user, fingerprint=fingerprint).exists():
            statement_import.duplicate_count += 1
            continue

        try:
            with db_transaction.atomic():
                category = categorize_from_description(statement_import.user, transaction_type, description_value)
                transaction = Transaction.objects.create(
                    user=statement_import.user,
                    category=category,
                    transaction_type=transaction_type,
                    date=date_value,
                    amount=amount_value if transaction_type == TransactionType.EXPENSE and row.get("transaction_type") else abs(amount_value),
                    currency=currency,
                    description=description_value,
                    notes=f"Imported from {statement_import.source_name or statement_import.file.name}",
                )
                ImportedTransaction.objects.create(
                    statement_import=statement_import,
                    transaction=transaction,
                    fingerprint=fingerprint,
                    raw_description=description_value,
                )
                statement_import.imported_count += 1
        except ValidationError:
            statement_import.skipped_count += 1

    statement_import.save(update_fields=["imported_count", "duplicate_count", "skipped_count", "updated_at"])
    return statement_import


def _normalize_transaction_type(raw_value, amount_value):
    if raw_value:
        normalized = str(raw_value).strip().lower()
        valid_types = {choice for choice, _ in TransactionType.choices}
        if normalized in valid_types:
            return normalized
        raise ValidationError(f"Unsupported transaction type '{raw_value}'.")
    return infer_transaction_type(amount_value)


def _lookup_category(user, category_name, transaction_type, allow_create=True):
    cleaned_name = (category_name or "").strip()
    if not cleaned_name:
        return categorize_from_description(user, transaction_type, "")
    category = Category.objects.filter(
        user=user,
        name__iexact=cleaned_name,
        transaction_type=transaction_type,
    ).first()
    if category:
        return category
    if not allow_create:
        raise ValidationError(
            f"Category '{cleaned_name}' does not exist for transaction type '{transaction_type}'."
        )
    return Category.objects.create(
        user=user,
        name=cleaned_name,
        transaction_type=transaction_type,
        is_active=True,
    )


def parse_bulk_csv_rows(file_obj):
    decoded = file_obj.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(decoded))
    for row in reader:
        yield {
            "date": row.get("date") or row.get("Date"),
            "amount": row.get("amount") or row.get("Amount"),
            "description": row.get("description") or row.get("Description") or "",
            "currency": row.get("currency") or row.get("Currency") or "INR",
            "transaction_type": row.get("transaction_type") or row.get("Transaction Type") or "",
            "category": row.get("category") or row.get("Category") or "",
            "notes": row.get("notes") or row.get("Notes") or "",
        }


def bulk_import_transactions(upload, currency_lookup):
    uploaded_file = upload.file
    uploaded_file.open("rb")
    rows = list(parse_bulk_csv_rows(uploaded_file))

    for row in rows:
        try:
            amount_value = Decimal(str(row["amount"]).replace(",", ""))
            if amount_value == 0:
                raise ValidationError("Amount cannot be zero.")
            transaction_type = _normalize_transaction_type(row.get("transaction_type"), amount_value)
            date_value = row.get("date")
            description_value = (row.get("description") or "Bulk imported transaction").strip()
            currency_code = (row.get("currency") or "INR").strip().upper()
            currency = currency_lookup(currency_code)
            category = _lookup_category(
                upload.user,
                row.get("category"),
                transaction_type,
                allow_create=True,
            )

            transaction = Transaction.objects.create(
                user=upload.user,
                category=category,
                transaction_type=transaction_type,
                date=date_value,
                amount=amount_value if transaction_type == TransactionType.EXPENSE else abs(amount_value),
                currency=currency,
                description=description_value,
                notes=(row.get("notes") or "").strip(),
            )
            ImportedTransaction.objects.create(
                statement_import=upload,
                transaction=transaction,
                fingerprint=fingerprint_row(date_value, transaction.amount, description_value, currency_code),
                raw_description=description_value,
            )
            upload.imported_count += 1
        except (InvalidOperation, TypeError, ValueError, ValidationError):
            upload.skipped_count += 1

    upload.save(update_fields=["imported_count", "duplicate_count", "skipped_count", "updated_at"])
    return upload
