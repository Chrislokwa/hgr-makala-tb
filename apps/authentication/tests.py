from django.test import TestCase
from django.urls import reverse
from apps.authentication.models import CustomUser, UserRole

class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='password123',
            first_name='Test',
            last_name='User',
            role=UserRole.MEDECIN,
            is_active=True
        )
        self.inactive_user = CustomUser.objects.create_user(
            username='inactiveuser',
            password='password123',
            first_name='Inactive',
            last_name='User',
            role=UserRole.MEDECIN,
            is_active=False
        )

    def test_login_page_renders(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'authentication/login.html')

    def test_login_success(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'password123'
        })
        self.assertRedirects(response, reverse('dashboard'))

    def test_login_invalid_password(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], None, "Identifiants incorrects.")

    def test_login_inactive_user(self):
        response = self.client.post(reverse('login'), {
            'username': 'inactiveuser',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], None, "Ce compte a été désactivé. Contactez votre administrateur.")

    def test_logout(self):
        self.client.login(username='testuser', password='password123')
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")
