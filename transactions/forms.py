from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from transactions.models import Category, Currency, StatementImport, Transaction


class CategoryForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = Category
        fields = ("name", "transaction_type", "is_active")

    def clean(self):
        cleaned_data = super().clean()
        name = (cleaned_data.get("name") or "").strip()
        transaction_type = cleaned_data.get("transaction_type")
        if self.user and name and transaction_type:
            existing = Category.objects.filter(
                user=self.user,
                transaction_type=transaction_type,
                name__iexact=name,
            )
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                self.add_error("name", "You already have a category with this name for this transaction type.")
        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.user:
            obj.user = self.user
        if commit:
            obj.save()
        return obj


class TransactionForm(forms.ModelForm):
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    allowed_receipt_types = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
    }
    max_receipt_size = 5 * 1024 * 1024

    class Meta:
        model = Transaction
        fields = (
            "transaction_type",
            "category",
            "date",
            "amount",
            "currency",
            "description",
            "receipt",
            "notes",
        )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.instance.user = self.user
        category_queryset = Category.objects.filter(user=self.user)
        if self.instance.pk and self.instance.category_id:
            category_queryset = category_queryset.filter(Q(is_active=True) | Q(pk=self.instance.category_id))
        else:
            category_queryset = category_queryset.filter(is_active=True)
        self.fields["category"].queryset = category_queryset.order_by("transaction_type", "name")
        self.fields["currency"].queryset = Currency.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        transaction_type = cleaned_data.get("transaction_type")
        category = cleaned_data.get("category")
        amount = cleaned_data.get("amount")
        receipt = cleaned_data.get("receipt")
        if category and transaction_type and category.transaction_type != transaction_type:
            self.add_error("category", "Selected category does not match the transaction type.")
        if amount is not None and transaction_type and amount < 0 and transaction_type != "expense":
            self.add_error("amount", "Negative amounts are only allowed for expense refunds.")
        if receipt:
            content_type = getattr(receipt, "content_type", "")
            if content_type not in self.allowed_receipt_types:
                self.add_error(
                    "receipt",
                    "Receipt must be a PDF, JPG, PNG, or WEBP file.",
                )
            if receipt.size > self.max_receipt_size:
                self.add_error("receipt", "Receipt file must be 5 MB or smaller.")
        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.user = self.user
        if commit:
            obj.save()
        return obj


class StatementImportForm(forms.ModelForm):
    class Meta:
        model = StatementImport
        fields = ("source_name", "file")

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        if not uploaded_file.name.lower().endswith((".csv", ".pdf")):
            raise forms.ValidationError("Upload a CSV or PDF statement.")
        if uploaded_file.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Statement file must be 5 MB or smaller.")
        return uploaded_file


class BulkTransactionUploadForm(forms.Form):
    source_name = forms.CharField(max_length=255, required=False)
    file = forms.FileField(
        help_text=(
            "Upload a CSV with columns like date, amount, description, currency, "
            "transaction_type, category, and notes."
        )
    )

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        if not uploaded_file.name.lower().endswith(".csv"):
            raise forms.ValidationError("Bulk upload currently supports CSV files only.")
        if uploaded_file.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Bulk upload file must be 5 MB or smaller.")
        return uploaded_file
