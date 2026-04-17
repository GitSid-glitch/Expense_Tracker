# Generated manually for budget alerts

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("budgets", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="BudgetAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("threshold", models.PositiveSmallIntegerField()),
                ("spent_amount", models.DecimalField(decimal_places=2, max_digits=14)),
                (
                    "budget",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alerts",
                        to="budgets.budget",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at",),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("budget", "threshold"),
                        name="unique_budget_threshold_alert",
                    )
                ],
            },
        ),
    ]
