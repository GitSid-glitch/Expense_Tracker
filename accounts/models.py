from django.conf import settings
from django.db import models

from core.models import TimestampedModel


class Profile(TimestampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    preferred_currency = models.CharField(max_length=3, default="INR")
    bio = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.username} profile"
