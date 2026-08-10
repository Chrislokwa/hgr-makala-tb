# pyrefly: ignore [missing-import]
from django.core.management.base import BaseCommand
# pyrefly: ignore [missing-import]
from apps.authentication.models import CustomUser, UserRole

class Command(BaseCommand):
    help = "Peuple la base de données avec les comptes de démonstration HGR Makala"

    def handle(self, *args, **options):
        demo_users = [
            {'prenom': 'Paul', 'nom': 'Kalombo', 'post_nom': 'Kanyinda', 'phone': '+243 81 234 5678', 'email': 'p.kalombo@hgr-makala.cd', 'role': UserRole.MEDECIN, 'is_active': True},
            {'prenom': 'Marthe', 'nom': 'Nzuzi', 'post_nom': '', 'phone': '+243 82 345 6789', 'email': 'm.nzuzi@hgr-makala.cd', 'role': UserRole.INFIRMIER, 'is_active': True},
            {'prenom': 'Serge', 'nom': 'Ilunga', 'post_nom': '', 'phone': '+243 83 456 7890', 'email': 's.ilunga@hgr-makala.cd', 'role': UserRole.LABORANTIN, 'is_active': True},
            {'prenom': 'Albert', 'nom': 'Mputu', 'post_nom': '', 'phone': '+243 84 567 8901', 'email': 'a.mputu@hgr-makala.cd', 'role': UserRole.STATISTICIEN, 'is_active': True},
            {'prenom': 'Judith', 'nom': 'Bongoy', 'post_nom': '', 'phone': '+243 85 678 9012', 'email': 'j.bongoy@hgr-makala.cd', 'role': UserRole.ADMIN, 'is_active': True, 'is_staff': True, 'is_superuser': True},
            {'prenom': 'Nadine', 'nom': 'Bakala', 'post_nom': '', 'phone': '+243 86 789 0123', 'email': 'n.bakala@hgr-makala.cd', 'role': UserRole.MEDECIN, 'is_active': True},
            {'prenom': 'Josué', 'nom': 'Mavungu', 'post_nom': '', 'phone': '+243 87 890 1234', 'email': 'j.mavungu@hgr-makala.cd', 'role': UserRole.INFIRMIER, 'is_active': True},
            {'prenom': 'Gisèle', 'nom': 'Mokolo', 'post_nom': '', 'phone': '+243 88 901 2345', 'email': 'g.mokolo@hgr-makala.cd', 'role': UserRole.LABORANTIN, 'is_active': True},
            {'prenom': 'Didier', 'nom': 'Kanza', 'post_nom': '', 'phone': '+243 89 012 3456', 'email': 'd.kanza@hgr-makala.cd', 'role': UserRole.MEDECIN, 'is_active': False},
            {'prenom': 'Éric', 'nom': 'Kabasele', 'post_nom': '', 'phone': '+243 80 123 4567', 'email': 'e.kabasele@hgr-makala.cd', 'role': UserRole.MEDECIN, 'is_active': False},
        ]

        count = 0
        for data in demo_users:
            email = data['email'].strip().lower()
            user, created = CustomUser.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'first_name': data['prenom'].strip(),
                    'post_nom': data['post_nom'].strip(),
                    'last_name': data['nom'].strip(),
                    'phone': data.get('phone') or None,
                    'role': data['role'],
                    'is_active': data['is_active'],
                    'is_staff': data.get('is_staff', False),
                    'is_superuser': data.get('is_superuser', False),
                }
            )
            if created:
                user.set_password('demo')
                user.save()
                count += 1
            else:
                user.username = email
                user.first_name = data['prenom'].strip()
                user.post_nom = data['post_nom'].strip()
                user.last_name = data['nom'].strip()
                user.phone = data.get('phone') or None
                user.role = data['role']
                user.is_active = data['is_active']
                user.set_password('demo')
                user.save()

        self.stdout.write(self.style.SUCCESS(f"Seed terminé. {count} nouveaux comptes créés / mis à jour. Mot de passe par défaut : demo"))
