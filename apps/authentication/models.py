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

    @property
    def display_name(self):
        full = f"{self.first_name} {self.last_name}".strip()
        return full if full else self.username

    @property
    def initials(self):
        name = self.display_name
        for prefix in ['Dr.', 'Inf.', 'Lab.']:
            if name.startswith(prefix):
                name = name[len(prefix):].strip()
        parts = name.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        elif parts and parts[0]:
            return parts[0][:2].upper()
        return self.username[:2].upper()

    @property
    def avatar_style(self):
        palettes = [
            ('#dbe7f3', '#375a83'),
            ('#e3efe4', '#2f6b46'),
            ('#f3e9d8', '#7d5a17'),
            ('#ece4f2', '#5f4b8b'),
            ('#f5e3e0', '#9a4632'),
            ('#e0efee', '#2a6f6f')
        ]
        h = 0
        for char in self.display_name:
            h = (h * 31 + ord(char)) % 997
        bg, text = palettes[h % len(palettes)]
        return f"--av:{bg};--avt:{text}"

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

        