from django.db import migrations, models

import transactions.models


class Migration(migrations.Migration):
    dependencies = [
        ("transactions", "0003_statementimport_importedtransaction"),
    ]

    operations = [
        migrations.AlterField(
            model_name="statementimport",
            name="file",
            field=models.FileField(upload_to=transactions.models.statement_upload_path),
        ),
    ]
