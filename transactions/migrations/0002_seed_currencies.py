from django.db import migrations


def seed_currencies(apps, schema_editor):
    Currency = apps.get_model("transactions", "Currency")
    currencies = [
        {"code": "INR", "name": "Indian Rupee", "symbol": "Rs", "exchange_rate_to_inr": "1.0000"},
        {"code": "USD", "name": "US Dollar", "symbol": "$", "exchange_rate_to_inr": "83.0000"},
        {"code": "EUR", "name": "Euro", "symbol": "EUR", "exchange_rate_to_inr": "90.0000"},
        {"code": "GBP", "name": "British Pound", "symbol": "GBP", "exchange_rate_to_inr": "105.0000"},
        {"code": "AED", "name": "UAE Dirham", "symbol": "AED", "exchange_rate_to_inr": "22.6000"},
    ]
    for currency in currencies:
        Currency.objects.update_or_create(code=currency["code"], defaults=currency)


def remove_currencies(apps, schema_editor):
    Currency = apps.get_model("transactions", "Currency")
    Currency.objects.filter(code__in=["INR", "USD", "EUR", "GBP", "AED"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("transactions", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_currencies, remove_currencies),
    ]
