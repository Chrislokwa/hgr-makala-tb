from django.test import TestCase
from django.urls import reverse
from django.core import mail
from apps.authentication.models import CustomUser, UserRole

class AuthenticationTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='adminuser',
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

    # Phase 4 — Gestion des utilisateurs
    def test_user_list_admin_access(self):
        self.client.login(username='adminuser', password='password123')
        response = self.client.get(reverse('user_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'authentication/user_list.html')

    def test_user_list_non_admin_denied(self):
        self.client.login(username='testuser', password='password123')
        response = self.client.get(reverse('user_list'))
        self.assertRedirects(response, reverse('dashboard'))

    def test_user_create_admin(self):
        self.client.login(username='adminuser', password='password123')
        response = self.client.post(reverse('user_create'), {
            'nom': 'Inf. Claire Bofassa',
            'username': 'cbofassa',
            'email': 'c.bofassa@hgr-makala.cd',
            'role': UserRole.INFIRMIER
        })
        self.assertRedirects(response, reverse('user_list'))
        created = CustomUser.objects.get(username='cbofassa')
        self.assertEqual(created.first_name, 'Inf.')
        self.assertEqual(created.last_name, 'Claire Bofassa')
        self.assertTrue(created.check_password('demo'))

    def test_user_update_admin(self):
        self.client.login(username='adminuser', password='password123')
        response = self.client.post(reverse('user_edit', kwargs={'pk': self.user.pk}), {
            'nom': 'Dr. Paul Kalombo Updated',
            'email': 'p.kalombo.new@hgr-makala.cd'
        })
        self.assertRedirects(response, reverse('user_list'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'p.kalombo.new@hgr-makala.cd')

    def test_user_toggle_active(self):
        self.client.login(username='adminuser', password='password123')
        response = self.client.post(reverse('user_toggle', kwargs={'pk': self.user.pk}))
        self.assertRedirects(response, reverse('user_list'))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_user_toggle_self_denied(self):
        self.client.login(username='adminuser', password='password123')
        response = self.client.post(reverse('user_toggle', kwargs={'pk': self.admin.pk}))
        self.assertRedirects(response, reverse('user_list'))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_user_toggle_last_admin_denied(self):
        self.client.login(username='adminuser', password='password123')
        # adminuser is the only active admin
        response = self.client.post(reverse('user_toggle', kwargs={'pk': self.admin.pk}))
        self.assertRedirects(response, reverse('user_list'))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_user_set_role(self):
        self.client.login(username='adminuser', password='password123')
        response = self.client.post(reverse('user_set_role', kwargs={'pk': self.user.pk}), {
            'role': UserRole.LABORANTIN
        })
        self.assertRedirects(response, reverse('user_list'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, UserRole.LABORANTIN)

    def test_user_set_role_last_admin_denied(self):
        self.client.login(username='adminuser', password='password123')
        response = self.client.post(reverse('user_set_role', kwargs={'pk': self.admin.pk}), {
            'role': UserRole.MEDECIN
        })
        self.assertRedirects(response, reverse('user_list'))
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, UserRole.ADMIN)
