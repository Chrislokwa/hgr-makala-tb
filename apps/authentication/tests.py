from django.test import TestCase
from django.urls import reverse
from django.core import mail
from apps.users.models import CustomUser, UserRole

class AuthenticationTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin@hgr-makala.cd',
            password='password123',
            email='admin@hgr-makala.cd',
            first_name='Judith',
            last_name='Bongoy',
            role=UserRole.ADMIN,
            is_active=True,
            is_staff=True,
            is_superuser=True
        )
        self.user = CustomUser.objects.create_user(
            username='testuser@hgr-makala.cd',
            password='password123',
            email='testuser@hgr-makala.cd',
            first_name='Test',
            last_name='User',
            role=UserRole.MEDECIN,
            is_active=True
        )
        self.inactive_user = CustomUser.objects.create_user(
            username='inactiveuser@hgr-makala.cd',
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
        self.assertContains(response, 'id="loginForm"')

    def test_login_success(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser@hgr-makala.cd',
            'password': 'password123'
        })
        self.assertRedirects(response, reverse('notification'))

    def test_login_invalid_password(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser@hgr-makala.cd',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Identifiants incorrects.")

    def test_login_empty_fields(self):
        response = self.client.post(reverse('login'), {
            'username': '',
            'password': ''
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Veuillez renseigner votre adresse e-mail et votre mot de passe.")

    def test_login_inactive_user(self):
        response = self.client.post(reverse('login'), {
            'username': 'inactiveuser@hgr-makala.cd',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ce compte a été désactivé. Contactez votre administrateur.")

    def test_logout(self):
        self.client.login(username='testuser@hgr-makala.cd', password='password123')
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))

    def test_logout_flushes_session(self):
        self.client.login(username='testuser@hgr-makala.cd', password='password123')
        self.client.post(reverse('logout'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_no_cache_headers(self):
        self.client.login(username='testuser@hgr-makala.cd', password='password123')
        response = self.client.get(reverse('notification'))
        self.assertEqual(response['Cache-Control'], 'no-cache, no-store, must-revalidate')
        self.assertEqual(response['Pragma'], 'no-cache')
        self.assertEqual(response['Expires'], '0')

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('notification'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('notification')}")

    # Phase 2 — Mot de passe oublié
    def test_password_reset_page_renders(self):
        response = self.client.get(reverse('password_reset'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="email"')

    def test_password_reset_submit(self):
        response = self.client.post(reverse('password_reset'), {
            'email': 'testuser@hgr-makala.cd'
        })
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Réinitialisation de votre mot de passe", mail.outbox[0].subject)

    # Phase 3 — Réinitialisation du mot de passe
    def test_password_change_authenticated(self):
        self.client.login(username='testuser@hgr-makala.cd', password='password123')
        response = self.client.get(reverse('password_change'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="old_password"')

        post_resp = self.client.post(reverse('password_change'), {
            'old_password': 'password123',
            'new_password1': 'newsecret123',
            'new_password2': 'newsecret123'
        })
        self.assertRedirects(post_resp, reverse('notification'))
