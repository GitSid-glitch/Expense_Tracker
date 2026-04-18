# Generated manually for statement import support

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("transactions", "0002_seed_currencies"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StatementImport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("file", models.FileField(upload_to="statements/user_uploads")),
                ("source_name", models.CharField(blank=True, max_length=255)),
                ("imported_count", models.PositiveIntegerField(default=0)),
                ("duplicate_count", models.PositiveIntegerField(default=0)),
                ("skipped_count", models.PositiveIntegerField(default=0)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="statement_imports", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="ImportedTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("fingerprint", models.CharField(max_length=64)),
                ("raw_description", models.CharField(blank=True, max_length=255)),
                ("statement_import", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="imported_transactions", to="transactions.statementimport")),
                ("transaction", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="import_record", to="transactions.transaction")),
            ],
            options={
                "ordering": ("-created_at",),
                "constraints": [
                    models.UniqueConstraint(fields=("statement_import", "fingerprint"), name="unique_import_fingerprint_per_statement")
                ],
            },
        ),
    ]
