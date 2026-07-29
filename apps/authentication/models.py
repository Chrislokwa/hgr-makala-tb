from django.contrib.auth.models import AbstractUser
from django.db import models

class UserRole(models.TextChoices):
    ADMIN = 'ADMIN', 'Administrateur'
    MEDECIN = 'MEDECIN', 'Médecin Traitant'
    INFIRMIER = 'INFIRMIER', 'Infirmier'
    LABORANTIN = 'LABORANTIN', 'Laborantin'
    STATISTICIEN = 'STATISTICIEN', 'Agent Statistique'

class CustomUser(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.INFIRMIER,
        help_text="Rôle de l'utilisateur dans le système HGR Makala"
    )
    phone = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

        