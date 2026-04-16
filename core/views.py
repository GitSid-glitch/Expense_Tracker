from calendar import month_name
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from budgets.models import Budget
from core.date_ranges import PERIOD_CHOICES, apply_budget_period, apply_transaction_period, resolve_period_filters
from transactions.models import Transaction
from transactions.services import (
    convert_amount,
    get_user_preferred_currency,
    quantize_money,
    summarize_transactions_in_currency,
)


@login_required
def dashboard_view(request):
    transactions = Transaction.objects.for_user(request.user).select_related("category", "currency")
    budgets = Budget.objects.filter(user=request.user).select_related("category")
    today = timezone.localdate()
    period_filters = resolve_period_filters(request.GET, today=today)
    filtered_transactions = apply_transaction_period(transactions, period_filters)
    filtered_budgets = apply_budget_period(budgets, period_filters)
    preferred_currency = get_user_preferred_currency(request.user)

    summary = summarize_transactions_in_currency(filtered_transactions, preferred_currency)
    income_total = summary["income"]
    expense_total = summary["expense"]
    investment_total = summary["investment"]
    savings = income_total - expense_total - investment_total

    category_totals = {}
    for transaction in filtered_transactions.expenses().select_related("currency"):
        key = transaction.category_snapshot or "Uncategorized"
        category_totals[key] = category_totals.get(key, Decimal("0.00")) + convert_amount(
            transaction.amount,
            transaction.currency,
            preferred_currency,
        )
    category_breakdown = [
        {"category_snapshot": key, "total": quantize_money(value)}
        for key, value in sorted(category_totals.items(), key=lambda item: item[1], reverse=True)
    ]

    monthly_totals = {}
    bucket_format = "%Y-%m-%d" if period_filters["chart_granularity"] == "day" else "%Y-%m"
    for transaction in filtered_transactions.select_related("currency"):
        bucket_key = transaction.date.strftime(bucket_format)
        if bucket_key not in monthly_totals:
            monthly_totals[bucket_key] = {
                "income": Decimal("0.00"),
                "expense": Decimal("0.00"),
                "investment": Decimal("0.00"),
            }
        monthly_totals[bucket_key][transaction.transaction_type] += convert_amount(
            transaction.amount,
            transaction.currency,
            preferred_currency,
        )
    monthly_trend = [
        {"label": month, "transaction_type": tx_type, "total": quantize_money(total)}
        for month, values in sorted(monthly_totals.items())
        for tx_type, total in values.items()
    ]
    timeline_years = {today.year}
    timeline_years.update(value.year for value in transactions.values_list("date", flat=True))
    timeline_years.update(value.year for value in budgets.values_list("month", flat=True))
    available_years = sorted(timeline_years, reverse=True)

    return render(
        request,
        "core/dashboard.html",
        {
            "income_total": income_total,
            "expense_total": expense_total,
            "investment_total": investment_total,
            "savings": savings,
            "category_breakdown": category_breakdown,
            "active_budgets": filtered_budgets,
            "latest_transactions": filtered_transactions[:10],
            "monthly_trend": monthly_trend,
            "preferred_currency": preferred_currency,
            "current_month_label": period_filters["label"],
            "selected_period": period_filters["period"],
            "selected_year": period_filters["year"],
            "selected_month": period_filters["month"],
            "selected_date_from": period_filters["date_from_value"],
            "selected_date_to": period_filters["date_to_value"],
            "period_choices": PERIOD_CHOICES,
            "available_years": available_years,
            "month_choices": [(index, month_name[index]) for index in range(1, 13)],
        },
    )
