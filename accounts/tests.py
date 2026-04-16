from django.contrib.auth.models import User
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from budgets.models import UserNotification


class ProfileSignalTests(TestCase):
    def test_profile_is_created_for_new_user(self):
        user = User.objects.create_user(username="alice", password="secret123")
        self.assertEqual(user.profile.preferred_currency, "INR")


class AuthViewsTests(TestCase):
    def test_signup_creates_user_and_profile(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "password1": "StrongPass123",
                "password2": "StrongPass123",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_profile_requires_login(self):
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 302)

    def test_login_page_loads(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

    @override_settings(GOOGLE_AUTH_ENABLED=False)
    def test_login_page_shows_google_setup_message_when_disabled(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "Google sign-in is ready in the app")

    @override_settings(GOOGLE_AUTH_ENABLED=True)
    def test_signup_page_shows_google_button_when_enabled(self):
        response = self.client.get(reverse("signup"))
        self.assertContains(response, "Sign up with Google")

    def test_navbar_shows_unread_notification_badge(self):
        user = User.objects.create_user(username="notifyuser", password="secret123")
        UserNotification.objects.create(
            user=user,
            title="Budget alert",
            message="You crossed your budget.",
        )
        self.client.login(username="notifyuser", password="secret123")
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Notifications")
        self.assertContains(response, "badge rounded-pill bg-danger")
        self.assertContains(response, "1")

    def test_profile_update_saves_user_and_profile_fields(self):
        user = User.objects.create_user(
            username="profileuser",
            password="secret123",
            email="old@example.com",
            first_name="Old",
            last_name="Name",
        )
        self.client.login(username="profileuser", password="secret123")
        response = self.client.post(
            reverse("profile"),
            {
                "first_name": "Siddharth",
                "last_name": "Shukla",
                "email": "siddharth@example.com",
                "username": "profileuser",
                "preferred_currency": "USD",
                "bio": "Backend developer focused on finance tooling.",
            },
        )
        self.assertRedirects(response, reverse("profile"))
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Siddharth")
        self.assertEqual(user.last_name, "Shukla")
        self.assertEqual(user.email, "siddharth@example.com")
        self.assertEqual(user.profile.preferred_currency, "USD")
        self.assertEqual(user.profile.bio, "Backend developer focused on finance tooling.")

    def test_profile_update_rejects_duplicate_email(self):
        User.objects.create_user(username="existing", password="secret123", email="taken@example.com")
        user = User.objects.create_user(username="profileuser", password="secret123", email="old@example.com")
        self.client.login(username="profileuser", password="secret123")
        response = self.client.post(
            reverse("profile"),
            {
                "first_name": "",
                "last_name": "",
                "email": "taken@example.com",
                "username": "profileuser",
                "preferred_currency": "INR",
                "bio": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email already exists.")
