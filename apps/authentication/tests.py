from django.test import TestCase
from django.urls import reverse
from django.core import mail
from apps.authentication.models import CustomUser, UserRole

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
        self.assertRedirects(response, reverse('dashboard'))

    def test_login_invalid_password(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser@hgr-makala.cd',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Identifiants incorrects.")

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

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

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
        self.assertRedirects(post_resp, reverse('dashboard'))

    # Phase 4 — Gestion des utilisateurs
    def test_user_list_admin_access(self):
        self.client.login(username='admin@hgr-makala.cd', password='password123')
        response = self.client.get(reverse('user_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="searchUser"')

    def test_user_list_non_admin_denied(self):
        self.client.login(username='testuser@hgr-makala.cd', password='password123')
        response = self.client.get(reverse('user_list'))
        self.assertRedirects(response, reverse('dashboard'))

    # Recherche asynchrone (HTMX)
    def test_user_list_async_search_returns_fragment(self):
        self.client.login(username='admin@hgr-makala.cd', password='password123')
        response = self.client.get(reverse('user_list'), {
            'q': 'testuser',
        }, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        # Fragment uniquement : la page entière n'est pas renvoyée.
        self.assertNotContains(response, 'id="searchUser"')
        # Le résultat filtré est présent.
        self.assertContains(response, 'testuser')

    def test_user_list_async_search_no_match(self):
        self.client.login(username='admin@hgr-makala.cd', password='password123')
        response = self.client.get(reverse('user_list'), {
            'q': 'introuvable',
        }, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aucun résultat')

    def test_user_list_async_search_denied_non_admin(self):
        self.client.login(username='testuser@hgr-makala.cd', password='password123')
        response = self.client.get(reverse('user_list'), {
            'q': 'admin',
        }, HTTP_HX_REQUEST='true')
        # La permission reste vérifiée côté serveur, même pour HTMX.
        self.assertRedirects(response, reverse('dashboard'))

    # Création / modification d'utilisateur
    def test_user_create_admin(self):
        self.client.login(username='admin@hgr-makala.cd', password='password123')
        response = self.client.post(reverse('user_create'), {
            'nom': 'Bofassa',
            'post_nom': '',
            'prenom': 'Claire',
            'email': 'c.bofassa@hgr-makala.cd',
            'phone': '+243 81 111 1111',
            'role': UserRole.INFIRMIER
        })
        self.assertRedirects(response, reverse('user_list'))
        created = CustomUser.objects.get(email='c.bofassa@hgr-makala.cd')
        self.assertEqual(created.username, 'c.bofassa@hgr-makala.cd')
        self.assertEqual(created.first_name, 'Claire')
        self.assertEqual(created.last_name, 'Bofassa')
        self.assertEqual(created.post_nom, '')
        self.assertEqual(created.phone, '+243 81 111 1111')
        self.assertEqual(created.role, UserRole.INFIRMIER)
        self.assertTrue(created.check_password('demo'))

    def test_user_create_sets_username_from_email(self):
        self.client.login(username='admin@hgr-makala.cd', password='password123')
        response = self.client.post(reverse('user_create'), {
            'nom': 'Kalombo',
            'post_nom': 'Kanyinda',
            'prenom': 'Paul',
            'email': 'P.KALOMBO@hgr-makala.cd',
            'phone': '',
            'role': UserRole.MEDECIN
        })
        self.assertRedirects(response, reverse('user_list'))
        created = CustomUser.objects.get(email='p.kalombo@hgr-makala.cd')
        self.assertEqual(created.username, 'p.kalombo@hgr-makala.cd')

    def test_user_create_strips_name_prefix(self):
        self.client.login(username='admin@hgr-makala.cd', password='password123')
        response = self.client.post(reverse('user_create'), {
            'nom': 'Dr. Kalombo',
            'post_nom': 'Kanyinda',
            'prenom': 'Paul',
            'email': 'p.kalombo@hgr-makala.cd',
            'phone': '',
            'role': UserRole.MEDECIN
        })
        self.assertRedirects(response, reverse('user_list'))
        created = CustomUser.objects.get(email='p.kalombo@hgr-makala.cd')
        self.assertEqual(created.last_name, 'Kalombo')
        self.assertEqual(created.titled_name, 'Dr. Paul Kalombo Kanyinda')

    def test_user_create_duplicate_email(self):
        self.client.login(username='admin@hgr-makala.cd', password='password123')
        response = self.client.post(reverse('user_create'), {
            'nom': 'Bongoy',
            'post_nom': '',
            'prenom': 'Judith',
            'email': 'admin@hgr-makala.cd',
            'phone': '',
            'role': UserRole.ADMIN
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cette adresse e-mail est déjà utilisée par un autre compte.")

    def test_user_update_admin(self):
        self.client.login(username='admin@hgr-makala.cd', password='password123')
        response = self.client.post(reverse('user_edit', kwargs={'pk': self.user.pk}), {
            'nom': 'Kalombo',
            'post_nom': 'Kanyinda',
            'prenom': 'Paul',
            'email': 'p.kalombo.new@hgr-makala.cd',
            'phone': '+243 82 222 2222'
        })
        self.assertRedirects(response, reverse('user_list'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'p.kalombo.new@hgr-makala.cd')
        self.assertEqual(self.user.username, 'p.kalombo.new@hgr-makala.cd')
        self.assertEqual(self.user.first_name, 'Paul')
        self.assertEqual(self.user.post_nom, 'Kanyinda')
        self.assertEqual(self.user.last_name, 'Kalombo')
        self.assertEqual(self.user.phone, '+243 82 222 2222')

    def test_user_toggle_active(self):
        self.client.login(username='admin@hgr-makala.cd', password='password123')
        response = self.client.post(reverse('user_toggle', kwargs={'pk': self.user.pk}))
        self.assertRedirects(response, reverse('user_list'))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_user_toggle_self_denied(self):
        self.client.login(username='admin@hgr-makala.cd', password='password123')
        response = self.client.post(reverse('user_toggle', kwargs={'pk': self.admin.pk}))
        self.assertRedirects(response, reverse('user_list'))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_user_toggle_last_admin_denied(self):
        self.client.login(username='admin@hgr-makala.cd', password='password123')
        # adminuser is the only active admin
        response = self.client.post(reverse('user_toggle', kwargs={'pk': self.admin.pk}))
        self.assertRedirects(response, reverse('user_list'))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_user_set_role(self):
        self.client.login(username='admin@hgr-makala.cd', password='password123')
        response = self.client.post(reverse('user_set_role', kwargs={'pk': self.user.pk}), {
            'role': UserRole.LABORANTIN
        })
        self.assertRedirects(response, reverse('user_list'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, UserRole.LABORANTIN)

    def test_user_set_role_last_admin_denied(self):
        self.client.login(username='admin@hgr-makala.cd', password='password123')
        response = self.client.post(reverse('user_set_role', kwargs={'pk': self.admin.pk}), {
            'role': UserRole.MEDECIN
        })
        self.assertRedirects(response, reverse('user_list'))
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, UserRole.ADMIN)

    # Abréviations gérées par le système selon le rôle
    def test_role_prefix_display(self):
        cases = [
            (UserRole.ADMIN, 'admin.'),
            (UserRole.MEDECIN, 'Dr.'),
            (UserRole.INFIRMIER, 'Inf.'),
            (UserRole.LABORANTIN, 'Lab.'),
            (UserRole.STATISTICIEN, 'Ags.'),
        ]
        for role, prefix in cases:
            u = CustomUser.objects.create_user(
                username=f'u{role}@test.cd',
                email=f'u{role}@test.cd',
                password='x1234567',
                first_name='Paul',
                last_name='Kalombo',
                post_nom='Kanyinda',
                role=role
            )
            self.assertEqual(u.role_prefix, prefix)
            self.assertEqual(u.titled_name, f"{prefix} Paul Kalombo Kanyinda")
            self.assertEqual(u.display_name, 'Paul Kalombo Kanyinda')

    def test_titled_name_without_full_name_falls_back_to_username(self):
        u = CustomUser.objects.create_user(
            username='j.doe@hgr-makala.cd',
            email='j.doe@hgr-makala.cd',
            password='x1234567',
            role=UserRole.STATISTICIEN
        )
        self.assertEqual(u.display_name, 'j.doe@hgr-makala.cd')
        self.assertEqual(u.titled_name, 'j.doe@hgr-makala.cd')
