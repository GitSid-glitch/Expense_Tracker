from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from transactions.models import Transaction
from transactions.services import convert_amount, get_user_preferred_currency, summarize_transactions_in_currency


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def finance_summary_api(request):
    transactions = Transaction.objects.for_user(request.user).select_related("currency")
    preferred_currency = get_user_preferred_currency(request.user)
    summary = summarize_transactions_in_currency(transactions, preferred_currency)
    return Response(
        {
            "currency": preferred_currency.code,
            "income": str(summary["income"]),
            "expense": str(summary["expense"]),
            "investment": str(summary["investment"]),
            "savings": str(summary["income"] - summary["expense"] - summary["investment"]),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def monthly_breakdown_api(request):
    transactions = Transaction.objects.for_user(request.user).select_related("currency")
    preferred_currency = get_user_preferred_currency(request.user)
    months = {}
    for transaction in transactions:
        month_key = transaction.date.strftime("%Y-%m")
        months.setdefault(month_key, {"income": 0.0, "expense": 0.0, "investment": 0.0})
        months[month_key][transaction.transaction_type] += float(
            convert_amount(transaction.amount, transaction.currency, preferred_currency)
        )
    return Response({"currency": preferred_currency.code, "months": months})
