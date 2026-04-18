from calendar import month_name
import csv
from collections import defaultdict
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from core.date_ranges import PERIOD_CHOICES, apply_transaction_period, resolve_period_filters
from transactions.models import Currency, Transaction
from transactions.services import (
    convert_amount,
    get_user_preferred_currency,
    quantize_money,
    summarize_transactions_in_currency,
)


@login_required
def monthly_report_view(request):
    transactions = Transaction.objects.for_user(request.user).select_related("currency", "category")
    period_filters = resolve_period_filters(request.GET)
    selected_type = request.GET.get("transaction_type")
    selected_currency = request.GET.get("currency")
    export_format = request.GET.get("export")
    if selected_type:
        transactions = transactions.filter(transaction_type=selected_type)
    if selected_currency:
        transactions = transactions.filter(currency__code=selected_currency.upper())
    transactions = apply_transaction_period(transactions, period_filters)
    preferred_currency = get_user_preferred_currency(request.user)

    totals = summarize_transactions_in_currency(transactions, preferred_currency)
    monthly_aggregate = defaultdict(
        lambda: {
            "income": Decimal("0.00"),
            "expense": Decimal("0.00"),
            "investment": Decimal("0.00"),
        }
    )
    category_aggregate = defaultdict(lambda: Decimal("0.00"))
    for transaction in transactions:
        month_key = transaction.date.strftime("%Y-%m")
        converted_amount = convert_amount(transaction.amount, transaction.currency, preferred_currency)
        monthly_aggregate[month_key][transaction.transaction_type] += converted_amount
        if transaction.transaction_type == "expense":
            category_aggregate[transaction.display_category] += converted_amount
    monthly_rows = [
        {"month": month, "transaction_type": tx_type, "total": quantize_money(total)}
        for month, values in sorted(monthly_aggregate.items())
        for tx_type, total in values.items()
    ]
    category_rows = [
        {"category": category, "total": quantize_money(total)}
        for category, total in sorted(category_aggregate.items(), key=lambda item: item[1], reverse=True)
    ]

    if export_format == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="monthly-report.csv"'
        writer = csv.writer(response)
        writer.writerow(["Month", "Transaction Type", f"Total ({preferred_currency.code})"])
        for row in monthly_rows:
            writer.writerow([row["month"], row["transaction_type"], row["total"]])
        return response

    return render(
        request,
        "reports/monthly_report.html",
        {
            "chart_rows": monthly_rows,
            "totals": totals,
            "selected_type": selected_type or "",
            "selected_currency": selected_currency or "",
            "date_from": period_filters["date_from_value"],
            "date_to": period_filters["date_to_value"],
            "preferred_currency": preferred_currency,
            "category_rows": category_rows,
            "selected_period": period_filters["period"],
            "selected_year": period_filters["year"],
            "selected_month": period_filters["month"],
            "period_label": period_filters["label"],
            "period_choices": PERIOD_CHOICES,
            "currency_choices": Currency.objects.filter(is_active=True),
            "available_years": sorted(
                {value.year for value in Transaction.objects.for_user(request.user).values_list("date", flat=True)}
                | {period_filters["year"]},
                reverse=True,
            ),
            "month_choices": [(index, month_name[index]) for index in range(1, 13)],
        },
    )
