from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from budgets.forms import BudgetForm
from budgets.models import Budget, UserNotification
from budgets.services import send_budget_alerts_for_budget


@login_required
def budget_list_view(request):
    budgets = Budget.objects.filter(user=request.user).select_related("category", "currency")
    return render(request, "budgets/budget_list.html", {"budgets": budgets})


@login_required
def budget_create_view(request):
    if request.method == "POST":
        form = BudgetForm(request.POST, user=request.user)
        if form.is_valid():
            budget = form.save()
            send_budget_alerts_for_budget(budget)
            messages.success(request, "Budget created successfully.")
            return redirect("budget-list")
    else:
        form = BudgetForm(user=request.user)
    return render(request, "budgets/budget_form.html", {"form": form, "title": "Add Budget"})


@login_required
def budget_update_view(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == "POST":
        form = BudgetForm(request.POST, instance=budget, user=request.user)
        if form.is_valid():
            budget = form.save()
            send_budget_alerts_for_budget(budget)
            messages.success(request, "Budget updated successfully.")
            return redirect("budget-list")
    else:
        form = BudgetForm(instance=budget, user=request.user)
    return render(request, "budgets/budget_form.html", {"form": form, "title": "Edit Budget"})


@login_required
def budget_delete_view(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == "POST":
        budget.delete()
        messages.success(request, "Budget deleted successfully.")
        return redirect("budget-list")
    return render(request, "budgets/budget_confirm_delete.html", {"budget": budget})


@login_required
def notification_list_view(request):
    notifications = UserNotification.objects.filter(user=request.user)
    notifications.filter(is_read=False).update(is_read=True, updated_at=timezone.now())
    notifications = notifications.order_by("-created_at")
    return render(
        request,
        "budgets/notification_list.html",
        {"notifications": notifications, "unread_count": 0},
    )


@login_required
def notification_mark_read_view(request, pk):
    notification = get_object_or_404(UserNotification, pk=pk, user=request.user)
    if request.method == "POST":
        notification.is_read = True
        notification.save(update_fields=["is_read", "updated_at"])
        messages.success(request, "Notification marked as read.")
    return redirect("notification-list")
