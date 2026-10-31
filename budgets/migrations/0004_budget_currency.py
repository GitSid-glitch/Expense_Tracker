import django.db.models.deletion
from django.db import migrations, models

import budgets.models


def set_existing_budget_currency(apps, schema_editor):
    Budget = apps.get_model("budgets", "Budget")
    Currency = apps.get_model("transactions", "Currency")
    inr = Currency.objects.get(code="INR")
    Budget.objects.filter(currency__isnull=True).update(currency_id=inr.pk)


class Migration(migrations.Migration):
    dependencies = [
        ("budgets", "0003_usernotification"),
        ("transactions", "0002_seed_currencies"),
    ]

    operations = [
        migrations.AddField(
            model_name="budget",
            name="currency",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="transactions.currency",
            ),
        ),
        migrations.RunPython(set_existing_budget_currency, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="budget",
            name="currency",
            field=models.ForeignKey(
                default=budgets.models.default_budget_currency,
                on_delete=django.db.models.deletion.PROTECT,
                to="transactions.currency",
            ),
        ),
    ]
