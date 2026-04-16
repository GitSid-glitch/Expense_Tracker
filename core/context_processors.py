from django.conf import settings

from budgets.models import UserNotification


def feature_flags(request):
    unread_notification_count = 0
    if getattr(request, "user", None) and request.user.is_authenticated:
        unread_notification_count = UserNotification.objects.filter(
            user=request.user,
            is_read=False,
        ).count()
    return {
        "google_auth_enabled": settings.GOOGLE_AUTH_ENABLED,
        "app_base_url": settings.APP_BASE_URL,
        "unread_notification_count": unread_notification_count,
    }
