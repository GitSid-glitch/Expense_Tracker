from django.contrib import admin

from accounts.models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "preferred_currency", "created_at")
    search_fields = ("user__username", "user__email")
