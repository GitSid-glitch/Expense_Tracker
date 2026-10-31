from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.sample_data import load_sample_workspace


class Command(BaseCommand):
    help = "Create a complete, deterministic demo workspace for local walkthroughs."

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            username="demo",
            defaults={
                "email": "demo@example.com",
                "first_name": "Demo",
                "last_name": "User",
            },
        )
        if created:
            user.set_password("demo12345")
            user.save()

        if load_sample_workspace(user):
            self.stdout.write(
                self.style.SUCCESS(
                    "Sample workspace ready: 6 months of activity, budgets, alerts and import history."
                )
            )
            self.stdout.write("Login with username 'demo' and password 'demo12345'.")
        elif user.profile.sample_data_loaded:
            self.stdout.write("Sample data is already loaded for this account.")
        else:
            self.stdout.write(
                self.style.WARNING(
                    "The demo account already contains transactions; existing records were left untouched."
                )
            )
