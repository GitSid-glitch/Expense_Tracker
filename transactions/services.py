from decimal import Decimal, ROUND_HALF_UP
from statistics import median

from transactions.models import Currency, TransactionType


TWOPLACES = Decimal("0.01")


def quantize_money(amount):
    return Decimal(amount).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def get_user_preferred_currency(user):
    code = getattr(getattr(user, "profile", None), "preferred_currency", "INR")
    return Currency.objects.filter(code=code, is_active=True).first() or Currency.objects.get(code="INR")


def convert_amount(amount, from_currency, to_currency):
    if from_currency.code == to_currency.code:
        return quantize_money(amount)
    amount_in_inr = Decimal(amount) * from_currency.exchange_rate_to_inr
    converted = amount_in_inr / to_currency.exchange_rate_to_inr
    return quantize_money(converted)


def summarize_transactions_in_currency(transactions, target_currency):
    summary = {
        TransactionType.INCOME: Decimal("0.00"),
        TransactionType.EXPENSE: Decimal("0.00"),
        TransactionType.INVESTMENT: Decimal("0.00"),
    }
    for transaction in transactions.select_related("currency"):
        summary[transaction.transaction_type] += convert_amount(
            transaction.amount,
            transaction.currency,
            target_currency,
        )
    return {key: quantize_money(value) for key, value in summary.items()}


def _quartiles(values):
    ordered = sorted(values)
    if len(ordered) < 2:
        value = ordered[0]
        return value, value, value

    mid = len(ordered) // 2
    if len(ordered) % 2 == 0:
        lower_half = ordered[:mid]
        upper_half = ordered[mid:]
    else:
        lower_half = ordered[:mid]
        upper_half = ordered[mid + 1 :]

    q2 = median(ordered)
    q1 = median(lower_half) if lower_half else ordered[0]
    q3 = median(upper_half) if upper_half else ordered[-1]
    return float(q1), float(q2), float(q3)


def _median_absolute_deviation(values, center):
    deviations = [abs(value - center) for value in values]
    return float(median(deviations)) if deviations else 0.0


def _anomaly_threshold(values):
    q1, center, q3 = _quartiles(values)
    iqr = q3 - q1
    iqr_threshold = q3 + (1.5 * iqr if iqr else center * 1.5)
    mad = _median_absolute_deviation(values, center)
    mad_threshold = center + (6 * mad if mad else center * 1.5)
    threshold = min(iqr_threshold, mad_threshold)
    return center, threshold


def detect_transaction_anomalies(transactions):
    expenses = [
        transaction
        for transaction in transactions.expenses().select_related("currency", "category")
        if not transaction.is_refund and transaction.amount > 0
    ]
    if not expenses:
        return []

    global_amounts = [float(transaction.amount_in_inr) for transaction in expenses]
    global_median, global_threshold = _anomaly_threshold(global_amounts)

    category_amounts = {}
    for transaction in expenses:
        category_key = transaction.display_category or "Uncategorized"
        category_amounts.setdefault(category_key, []).append(float(transaction.amount_in_inr))

    anomalies = []
    for transaction in expenses:
        amount_in_inr = float(transaction.amount_in_inr)
        category_key = transaction.display_category or "Uncategorized"
        category_values = category_amounts.get(category_key, [])
        if len(category_values) >= 4:
            baseline_median, threshold = _anomaly_threshold(category_values)
            baseline_scope = f"{category_key} category history"
            baseline_explanation = f"Used category history because {category_key} has {len(category_values)} expense records."
        else:
            baseline_median = global_median
            threshold = global_threshold
            baseline_scope = "overall expense history"
            baseline_explanation = (
                f"Used overall expense history because {category_key} has only {len(category_values)} expense record"
                f"{'' if len(category_values) == 1 else 's'}."
            )

        if threshold and amount_in_inr > threshold and amount_in_inr > baseline_median:
            anomalies.append(
                {
                    "transaction": transaction,
                    "amount_in_inr": round(amount_in_inr, 2),
                    "baseline_median_in_inr": round(baseline_median, 2),
                    "threshold_in_inr": round(threshold, 2),
                    "baseline_scope": baseline_scope,
                    "baseline_explanation": baseline_explanation,
                }
            )
    return sorted(anomalies, key=lambda item: item["amount_in_inr"], reverse=True)
