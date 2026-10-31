from django.conf import settings
from django.core.mail import send_mail

from budgets.models import BudgetAlert, UserNotification


def send_budget_alerts_for_budget(budget):
    percentage = float(budget.usage_percentage)
    triggered = []

    for threshold in (80, 100):
        if percentage >= threshold and not BudgetAlert.objects.filter(budget=budget, threshold=threshold).exists():
            spent_amount = budget.spent_amount
            budget_alert = BudgetAlert.objects.create(
                budget=budget,
                threshold=threshold,
                spent_amount=spent_amount,
            )
            UserNotification.objects.create(
                user=budget.user,
                title=f"Budget alert for {budget.category.name}",
                message=(
                    f"Your {budget.category.name} budget for {budget.month:%B %Y} has reached {threshold}% usage. "
                    f"Spent: {spent_amount} {budget.currency.code}. Limit: {budget.limit_amount} {budget.currency.code}."
                ),
                related_budget_alert=budget_alert,
            )
            subject = f"Budget alert: {budget.category.name} reached {threshold}%"
            message = (
                f"Hello {budget.user.username},\n\n"
                f"Your budget for {budget.category.name} in {budget.month:%B %Y} has reached {threshold}%.\n"
                f"Budget limit: {budget.limit_amount}\n"
                f"Spent so far: {spent_amount}\n"
                f"Current usage: {budget.usage_percentage:.2f}%\n"
            )
            send_mail(
                subject,
                message,
                getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                [budget.user.email] if budget.user.email else ["demo@example.com"],
                fail_silently=True,
            )
            triggered.append(threshold)

    return triggered
