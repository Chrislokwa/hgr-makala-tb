# pyrefly: ignore [missing-import]
from django.contrib.auth.models import AbstractUser
# pyrefly: ignore [missing-import]
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
    post_nom = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    ROLE_PREFIXES = {
        UserRole.ADMIN: 'admin.',
        UserRole.MEDECIN: 'Dr.',
        UserRole.INFIRMIER: 'Inf.',
        UserRole.LABORANTIN: 'Lab.',
        UserRole.STATISTICIEN: 'Ags.',
    }

    @classmethod
    def strip_name_prefix(cls, value):
        if not value:
            return value
        value = value.strip()
        for prefix in cls.ROLE_PREFIXES.values():
            if value.lower().startswith(prefix.lower()):
                return value[len(prefix):].strip()
        return value

    @property
    def display_name(self):
        full = " ".join(
            part for part in (self.first_name, self.last_name, self.post_nom) if part
        ).strip()
        return full if full else self.username

    @property
    def role_prefix(self):
        return self.ROLE_PREFIXES.get(self.role, '')

    @property
    def titled_name(self):
        full = self.display_name
        if not full or full == self.username:
            return self.username
        prefix = self.role_prefix
        return f"{prefix} {full}".strip() if prefix else full

    @property
    def initials(self):
        parts = self.display_name.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        elif parts and parts[0]:
            return parts[0][:2].upper()
        return self.username[:2].upper()

    @property
    def avatar_palette(self):
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
        return palettes[h % len(palettes)]

    @property
    def avatar_bg(self):
        return self.avatar_palette[0]

    @property
    def avatar_text(self):
        return self.avatar_palette[1]

    @property
    def avatar_style(self):
        bg, text = self.avatar_palette
        return f"--av:{bg};--avt:{text}"

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

        