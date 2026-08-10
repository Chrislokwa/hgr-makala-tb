from django.test import TestCase
from django.urls import reverse
from django.core import mail
from apps.authentication.models import CustomUser, UserRole

class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='password123',
            email='testuser@hgr-makala.cd',
            first_name='Test',
            last_name='User',
            role=UserRole.MEDECIN,
            is_active=True
        )
        self.inactive_user = CustomUser.objects.create_user(
            username='inactiveuser',
            password='password123',
            email='inactiveuser@hgr-makala.cd',
            first_name='Inactive',
            last_name='User',
            role=UserRole.MEDECIN,
            is_active=False
        )

    # Phase 1
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

    # Phase 2 — Mot de passe oublié
    def test_password_reset_page_renders(self):
        response = self.client.get(reverse('password_reset'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'authentication/password_reset.html')

    def test_password_reset_submit(self):
        response = self.client.post(reverse('password_reset'), {
            'email': 'testuser@hgr-makala.cd'
        })
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Réinitialisation de votre mot de passe", mail.outbox[0].subject)

    # Phase 3 — Réinitialisation du mot de passe
    def test_password_change_authenticated(self):
        self.client.login(username='testuser', password='password123')
        response = self.client.get(reverse('password_change'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'authentication/password_change.html')

        post_resp = self.client.post(reverse('password_change'), {
            'old_password': 'password123',
            'new_password1': 'newsecret123',
            'new_password2': 'newsecret123'
        })
        self.assertRedirects(post_resp, reverse('dashboard'))
        # verify user can login with new password
        self.client.logout()
        login_resp = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'newsecret123'
        })
        self.assertRedirects(login_resp, reverse('dashboard'))
