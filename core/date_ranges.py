from calendar import month_name
from datetime import date

from django.utils import timezone
from django.utils.dateparse import parse_date


PERIOD_MONTH = "month"
PERIOD_YEAR = "year"
PERIOD_ALL = "all"
PERIOD_CUSTOM = "custom"
VALID_PERIODS = {PERIOD_MONTH, PERIOD_YEAR, PERIOD_ALL, PERIOD_CUSTOM}
PERIOD_CHOICES = (
    (PERIOD_MONTH, "Month"),
    (PERIOD_YEAR, "Year"),
    (PERIOD_ALL, "All time"),
    (PERIOD_CUSTOM, "Custom range"),
)


def _coerce_int(raw_value, default, minimum, maximum):
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    return min(max(value, minimum), maximum)


def resolve_period_filters(params, today=None):
    today = today or timezone.localdate()
    period = params.get("period", PERIOD_MONTH)
    if period not in VALID_PERIODS:
        period = PERIOD_MONTH

    year = _coerce_int(params.get("year"), today.year, 2000, today.year + 10)
    month = _coerce_int(params.get("month"), today.month, 1, 12)
    raw_date_from = (params.get("date_from") or "").strip()
    raw_date_to = (params.get("date_to") or "").strip()
    date_from = parse_date(raw_date_from) if raw_date_from else None
    date_to = parse_date(raw_date_to) if raw_date_to else None

    if period == PERIOD_CUSTOM and date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from

    if period == PERIOD_MONTH:
        label = f"{month_name[month]} {year}"
    elif period == PERIOD_YEAR:
        label = str(year)
    elif period == PERIOD_ALL:
        label = "All Time"
    else:
        if date_from and date_to:
            label = f"{date_from:%b %d, %Y} to {date_to:%b %d, %Y}"
        elif date_from:
            label = f"From {date_from:%b %d, %Y}"
        elif date_to:
            label = f"Until {date_to:%b %d, %Y}"
        else:
            period = PERIOD_MONTH
            label = f"{month_name[month]} {year}"

    return {
        "period": period,
        "year": year,
        "month": month,
        "date_from": date_from,
        "date_to": date_to,
        "date_from_value": date_from.isoformat() if date_from else "",
        "date_to_value": date_to.isoformat() if date_to else "",
        "label": label,
        "chart_granularity": "day" if period == PERIOD_MONTH else "month",
    }


def apply_transaction_period(queryset, filters):
    period = filters["period"]
    if period == PERIOD_MONTH:
        return queryset.filter(date__year=filters["year"], date__month=filters["month"])
    if period == PERIOD_YEAR:
        return queryset.filter(date__year=filters["year"])
    if period == PERIOD_CUSTOM:
        if filters["date_from"]:
            queryset = queryset.filter(date__gte=filters["date_from"])
        if filters["date_to"]:
            queryset = queryset.filter(date__lte=filters["date_to"])
    return queryset


def apply_budget_period(queryset, filters):
    period = filters["period"]
    if period == PERIOD_MONTH:
        return queryset.filter(month__year=filters["year"], month__month=filters["month"])
    if period == PERIOD_YEAR:
        return queryset.filter(month__year=filters["year"])
    if period == PERIOD_CUSTOM:
        if filters["date_from"]:
            queryset = queryset.filter(
                month__gte=date(filters["date_from"].year, filters["date_from"].month, 1)
            )
        if filters["date_to"]:
            queryset = queryset.filter(
                month__lte=date(filters["date_to"].year, filters["date_to"].month, 1)
            )
    return queryset
