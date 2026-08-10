from django.core.management.base import BaseCommand
from apps.authentication.models import CustomUser, UserRole

class Command(BaseCommand):
    help = "Peuple la base de données avec les comptes de démonstration HGR Makala"

    def handle(self, *args, **options):
        demo_users = [
            {'username': 'pkalombo', 'nom': 'Dr. Paul Kalombo', 'email': 'p.kalombo@hgr-makala.cd', 'role': UserRole.MEDECIN, 'is_active': True},
            {'username': 'mnzuzi', 'nom': 'Inf. Marthe Nzuzi', 'email': 'm.nzuzi@hgr-makala.cd', 'role': UserRole.INFIRMIER, 'is_active': True},
            {'username': 'silunga', 'nom': 'Lab. Serge Ilunga', 'email': 's.ilunga@hgr-makala.cd', 'role': UserRole.LABORANTIN, 'is_active': True},
            {'username': 'amputu', 'nom': 'Albert Mputu', 'email': 'a.mputu@hgr-makala.cd', 'role': UserRole.STATISTICIEN, 'is_active': True},
            {'username': 'jbongoy', 'nom': 'Judith Bongoy', 'email': 'j.bongoy@hgr-makala.cd', 'role': UserRole.ADMIN, 'is_active': True, 'is_staff': True, 'is_superuser': True},
            {'username': 'nbakala', 'nom': 'Dr. Nadine Bakala', 'email': 'n.bakala@hgr-makala.cd', 'role': UserRole.MEDECIN, 'is_active': True},
            {'username': 'jmavungu', 'nom': 'Inf. Josué Mavungu', 'email': 'j.mavungu@hgr-makala.cd', 'role': UserRole.INFIRMIER, 'is_active': True},
            {'username': 'gmokolo', 'nom': 'Lab. Gisèle Mokolo', 'email': 'g.mokolo@hgr-makala.cd', 'role': UserRole.LABORANTIN, 'is_active': True},
            {'username': 'dkanza', 'nom': 'Dr. Didier Kanza', 'email': 'd.kanza@hgr-makala.cd', 'role': UserRole.MEDECIN, 'is_active': False},
            {'username': 'ekabasele', 'nom': 'Dr. Éric Kabasele', 'email': 'e.kabasele@hgr-makala.cd', 'role': UserRole.MEDECIN, 'is_active': False},
        ]

        count = 0
        for data in demo_users:
            nom = data.pop('nom')
            parts = nom.split(' ', 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ''

            user, created = CustomUser.objects.get_or_create(
                username=data['username'],
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': data['email'],
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
                user.first_name = first_name
                user.last_name = last_name
                user.email = data['email']
                user.role = data['role']
                user.is_active = data['is_active']
                user.set_password('demo')
                user.save()

        self.stdout.write(self.style.SUCCESS(f"Seed terminé. {count} nouveaux comptes créés / mis à jour. Mot de passe par défaut : demo"))
