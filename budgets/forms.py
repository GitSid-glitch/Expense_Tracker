from django import forms
from datetime import date

from budgets.models import Budget
from transactions.models import Category, Currency, TransactionType


class BudgetForm(forms.ModelForm):
    month = forms.DateField(
        input_formats=["%Y-%m"],
        widget=forms.DateInput(
            attrs={"type": "month"},
            format="%Y-%m",
        ),
    )

    class Meta:
        model = Budget
        fields = ("category", "month", "limit_amount", "currency")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.instance.user = self.user
        if self.instance.pk and self.instance.month:
            self.initial["month"] = self.instance.month.strftime("%Y-%m")
        category_queryset = Category.objects.filter(
            user=self.user,
            transaction_type=TransactionType.EXPENSE,
        )
        if self.instance.pk and self.instance.category_id:
            category_queryset = category_queryset.filter(pk=self.instance.category_id) | category_queryset.filter(
                is_active=True
            )
        else:
            category_queryset = category_queryset.filter(is_active=True)
        self.fields["category"].queryset = category_queryset.order_by("name")
        self.fields["currency"].queryset = Currency.objects.filter(is_active=True).order_by("code")
        if not self.instance.pk:
            preferred_code = getattr(self.user.profile, "preferred_currency", "INR")
            self.initial["currency"] = (
                Currency.objects.filter(code=preferred_code, is_active=True).first()
                or Currency.objects.get(code="INR")
            )

    def clean_month(self):
        month = self.cleaned_data["month"]
        return date(month.year, month.month, 1)

    def clean_limit_amount(self):
        limit_amount = self.cleaned_data["limit_amount"]
        if limit_amount <= 0:
            raise forms.ValidationError("Budget limit must be greater than zero.")
        return limit_amount

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get("category")
        month = cleaned_data.get("month")
        if not category or not month:
            return cleaned_data

        existing_budget = Budget.objects.filter(
            user=self.user,
            category=category,
            month=month,
        )
        if self.instance.pk:
            existing_budget = existing_budget.exclude(pk=self.instance.pk)
        if existing_budget.exists():
            raise forms.ValidationError(
                "A budget already exists for this category and month."
            )
        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.user = self.user
        if commit:
            obj.save()
        return obj
