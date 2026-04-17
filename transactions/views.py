import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from budgets.models import Budget
from budgets.services import send_budget_alerts_for_budget
from transactions.forms import BulkTransactionUploadForm, CategoryForm, StatementImportForm, TransactionForm
from transactions.importers import bulk_import_transactions, import_statement
from transactions.models import Category, Currency, StatementImport, Transaction, TransactionType
from transactions.services import detect_transaction_anomalies


def _trigger_budget_notifications(transaction):
    if transaction.transaction_type != TransactionType.EXPENSE or not transaction.category:
        return
    budget = Budget.objects.filter(
        user=transaction.user,
        category=transaction.category,
        month__year=transaction.date.year,
        month__month=transaction.date.month,
    ).first()
    if budget:
        send_budget_alerts_for_budget(budget)


@login_required
def transaction_list_view(request):
    transactions = Transaction.objects.for_user(request.user).select_related("category", "currency")
    categories = Category.objects.filter(user=request.user).order_by("transaction_type", "name")
    currencies = Currency.objects.filter(is_active=True).order_by("code")
    selected_type = request.GET.get("transaction_type")
    selected_category = request.GET.get("category")
    selected_currency = request.GET.get("currency")
    selected_refund = request.GET.get("refund")
    amount_min = request.GET.get("amount_min")
    amount_max = request.GET.get("amount_max")
    search = request.GET.get("search")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    if selected_type:
        transactions = transactions.filter(transaction_type=selected_type)
    if selected_category:
        transactions = transactions.filter(category_id=selected_category)
    if selected_currency:
        transactions = transactions.filter(currency__code=selected_currency)
    if selected_refund == "yes":
        transactions = transactions.filter(is_refund=True)
    elif selected_refund == "no":
        transactions = transactions.filter(is_refund=False)
    if amount_min:
        transactions = transactions.filter(amount__gte=amount_min)
    if amount_max:
        transactions = transactions.filter(amount__lte=amount_max)
    if search:
        transactions = transactions.filter(
            Q(description__icontains=search)
            | Q(notes__icontains=search)
            | Q(category_snapshot__icontains=search)
            | Q(category__name__icontains=search)
        )
    if date_from:
        transactions = transactions.filter(date__gte=date_from)
    if date_to:
        transactions = transactions.filter(date__lte=date_to)
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="transactions.csv"'
        writer = csv.writer(response)
        writer.writerow(["Date", "Type", "Category", "Description", "Amount", "Currency", "Receipt"])
        for transaction in transactions:
            writer.writerow(
                [
                    transaction.date,
                    transaction.transaction_type,
                    transaction.display_category,
                    transaction.description,
                    transaction.amount,
                    transaction.currency.code,
                    transaction.receipt.url if transaction.receipt else "",
                ]
            )
        return response
    return render(
        request,
        "transactions/transaction_list.html",
        {
            "transactions": transactions,
            "categories": categories,
            "currencies": currencies,
            "selected_type": selected_type or "",
            "selected_category": selected_category or "",
            "selected_currency": selected_currency or "",
            "selected_refund": selected_refund or "",
            "amount_min": amount_min or "",
            "amount_max": amount_max or "",
            "search": search or "",
            "date_from": date_from or "",
            "date_to": date_to or "",
        },
    )


@login_required
def statement_import_view(request):
    imports = StatementImport.objects.filter(user=request.user)
    if request.method == "POST":
        form = StatementImportForm(request.POST, request.FILES)
        if form.is_valid():
            statement_import = form.save(commit=False)
            statement_import.user = request.user
            statement_import.save()

            def currency_lookup(code):
                return Currency.objects.filter(code=code, is_active=True).first() or Currency.objects.get(code="INR")

            import_statement(statement_import, currency_lookup)
            messages.success(request, "Statement processed successfully.")
            return redirect("statement-import")
    else:
        form = StatementImportForm()

    return render(
        request,
        "transactions/statement_import.html",
        {"form": form, "imports": imports},
    )


@login_required
def transaction_bulk_upload_view(request):
    uploads = StatementImport.objects.filter(user=request.user, source_name__startswith="Bulk upload:")
    if request.method == "POST":
        form = BulkTransactionUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = StatementImport.objects.create(
                user=request.user,
                source_name=f"Bulk upload: {form.cleaned_data.get('source_name') or form.cleaned_data['file'].name}",
                file=form.cleaned_data["file"],
            )

            def currency_lookup(code):
                return Currency.objects.filter(code=code, is_active=True).first() or Currency.objects.get(code="INR")

            bulk_import_transactions(upload, currency_lookup)
            messages.success(
                request,
                f"Bulk upload processed. Imported {upload.imported_count} transactions and skipped {upload.skipped_count}.",
            )
            return redirect("transaction-bulk-upload")
    else:
        form = BulkTransactionUploadForm()

    return render(
        request,
        "transactions/transaction_bulk_upload.html",
        {"form": form, "uploads": uploads},
    )


@login_required
def anomalies_view(request):
    transactions = Transaction.objects.for_user(request.user)
    anomalies = detect_transaction_anomalies(transactions)
    return render(request, "transactions/anomalies.html", {"anomalies": anomalies})


@login_required
def transaction_create_view(request):
    if request.method == "POST":
        form = TransactionForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            transaction = form.save()
            _trigger_budget_notifications(transaction)
            messages.success(request, "Transaction added successfully.")
            return redirect("transaction-list")
    else:
        form = TransactionForm(user=request.user)
    return render(request, "transactions/transaction_form.html", {"form": form, "title": "Add Transaction"})


@login_required
def transaction_update_view(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == "POST":
        form = TransactionForm(request.POST, request.FILES, instance=transaction, user=request.user)
        if form.is_valid():
            transaction = form.save()
            _trigger_budget_notifications(transaction)
            messages.success(request, "Transaction updated successfully.")
            return redirect("transaction-list")
    else:
        form = TransactionForm(instance=transaction, user=request.user)
    return render(request, "transactions/transaction_form.html", {"form": form, "title": "Edit Transaction"})


@login_required
def transaction_delete_view(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == "POST":
        transaction.delete()
        messages.success(request, "Transaction deleted successfully.")
        return redirect("transaction-list")
    return render(request, "transactions/transaction_confirm_delete.html", {"transaction": transaction})


@login_required
def category_list_view(request):
    categories = Category.objects.filter(user=request.user).order_by("transaction_type", "name")
    return render(request, "transactions/category_list.html", {"categories": categories})


@login_required
def category_create_view(request):
    if request.method == "POST":
        form = CategoryForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Category added successfully.")
            return redirect("category-list")
    else:
        form = CategoryForm(user=request.user)
    return render(request, "transactions/category_form.html", {"form": form, "title": "Add Category"})


@login_required
def category_update_view(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated successfully.")
            return redirect("category-list")
    else:
        form = CategoryForm(instance=category, user=request.user)
    return render(request, "transactions/category_form.html", {"form": form, "title": "Edit Category"})


@login_required
def category_delete_view(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    linked_count = category.transactions.count()
    linked_budget_count = category.budgets.count()
    if request.method == "POST":
        category.delete()
        if linked_count or linked_budget_count:
            impact_parts = []
            if linked_count:
                impact_parts.append(f"preserved {linked_count} linked transactions")
            if linked_budget_count:
                impact_parts.append(f"removed {linked_budget_count} linked budgets")
            messages.warning(request, f"Deleted category and {' while '.join(impact_parts)}.")
        else:
            messages.success(request, "Category deleted successfully.")
        return redirect("category-list")
    return render(
        request,
        "transactions/category_confirm_delete.html",
        {"category": category, "linked_count": linked_count, "linked_budget_count": linked_budget_count},
    )
