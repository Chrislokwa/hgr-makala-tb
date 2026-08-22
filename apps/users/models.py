# pyrefly: ignore [missing-import]
from django.contrib.auth.models import AbstractUser
# pyrefly: ignore [missing-import]
from django.db import models
from django.conf import settings
from django.utils import timezone

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


class AuditLog(models.Model):
    class Action(models.TextChoices):
        LOGIN = 'LOGIN', 'Connexion'
        LOGOUT = 'LOGOUT', 'Déconnexion'
        CREATE_USER = 'CREATE_USER', 'Création utilisateur'
        UPDATE_USER = 'UPDATE_USER', 'Modification utilisateur'
        TOGGLE_USER = 'TOGGLE_USER', 'Activation/Désactivation'
        CHANGE_ROLE = 'CHANGE_ROLE', 'Changement de rôle'
        CREATE_PATIENT = 'CREATE_PATIENT', 'Création dossier patient'
        UPDATE_PATIENT = 'UPDATE_PATIENT', 'Modification dossier'
        FINALIZE_ADMISSION = 'FINALIZE_ADMISSION', 'Finalisation admission'
        PRESCRIPTION = 'PRESCRIPTION', 'Prescription examen'
        RESULTAT_SAISIE = 'RESULTAT_SAISIE', 'Saisie résultats labo'
        INTERPRETATION = 'INTERPRETATION', 'Interprétation médicale'
        OBSERVANCE = 'OBSERVANCE', 'Saisie observance'
        VISITE = 'VISITE', 'Visite de suivi'
        MODIFICATION_TRAITEMENT = 'MODIFICATION_TRAITEMENT', 'Modification traitement'
        RDV_CREATE = 'RDV_CREATE', 'Création rendez-vous'
        RDV_STATUS = 'RDV_STATUS', 'Statut rendez-vous'
        CLOTURE = 'CLOTURE', 'Clôture dossier'
        CONSULTATION = 'CONSULTATION', 'Consultation'
        EXPORT = 'EXPORT', 'Export rapport'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    username_snapshot = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=30, choices=Action.choices, db_index=True)
    description = models.TextField()
    target_model = models.CharField(max_length=50, blank=True)
    target_id = models.CharField(max_length=50, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    extra = models.JSONField(default=dict, blank=True)

    ACTION_COLORS = {
        'LOGIN': '#2e7d32',
        'LOGOUT': '#616161',
        'CREATE_USER': '#1565c0',
        'UPDATE_USER': '#1976d2',
        'TOGGLE_USER': '#ef6c00',
        'CHANGE_ROLE': '#4e342e',
        'CREATE_PATIENT': '#1b5e20',
        'UPDATE_PATIENT': '#0d47a1',
        'FINALIZE_ADMISSION': '#00695c',
        'PRESCRIPTION': '#6a1b9a',
        'RESULTAT_SAISIE': '#283593',
        'INTERPRETATION': '#00838f',
        'OBSERVANCE': '#f57f17',
        'VISITE': '#006064',
        'MODIFICATION_TRAITEMENT': '#ad1457',
        'RDV_CREATE': '#33691e',
        'RDV_STATUS': '#4527a0',
        'CLOTURE': '#b71c1c',
        'CONSULTATION': '#37474f',
        'EXPORT': '#3e2723',
    }

    @property
    def action_color(self):
        return self.ACTION_COLORS.get(self.action, '#5f6368')

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Journal'
        verbose_name_plural = 'Journaux'

    def __str__(self):
        return f"[{self.timestamp:%d/%m/%Y %H:%M}] {self.username_snapshot or self.user} — {self.get_action_display()}"


def audit_log(user, action, description, request=None, target=None, extra=None):
    """Helper centralisé pour tracer une action utilisateur."""
    try:
        ip = None
        if request is not None:
            ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR')
            # normalize
            if ip and len(ip) > 45:
                ip = ip[:45]
            try:
                # validate IP, fallback to None if invalid
                import ipaddress
                ipaddress.ip_address(ip)
            except Exception:
                ip = None
        target_model = ''
        target_id = ''
        if target is not None:
            target_model = target.__class__.__name__
            try:
                target_id = str(target.pk)
            except Exception:
                target_id = ''
        # Snapshot format demandé : Nom + postnom + prenom (sans préfixe)
        snapshot = ''
        if user and hasattr(user, 'last_name'):
            snapshot = ' '.join(part for part in (user.last_name, user.post_nom, user.first_name) if part).strip()
        if not snapshot:
            snapshot = getattr(user, 'username', '') or ''
        AuditLog.objects.create(
            user=user if user and getattr(user, 'is_authenticated', False) else None,
            username_snapshot=snapshot,
            action=action,
            description=description,
            target_model=target_model,
            target_id=target_id,
            ip_address=ip,
            extra=extra or {},
        )
    except Exception:
        # Ne jamais bloquer le flux métier à cause du log
        pass
