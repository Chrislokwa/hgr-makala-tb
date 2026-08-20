from apps.users.models import UserRole
from apps.users.permissions import RoleRequiredMixin


class MedecinRequiredMixin(RoleRequiredMixin):
    allowed_roles = [UserRole.MEDECIN]


class LaborantinRequiredMixin(RoleRequiredMixin):
    allowed_roles = [UserRole.LABORANTIN]


class InfirmierRequiredMixin(RoleRequiredMixin):
    allowed_roles = [UserRole.INFIRMIER]


class PersonnelAutoriseMixin(RoleRequiredMixin):
    """Accès aux dossiers patients pour le personnel autorisé (US3.3 / US3.4).

    Médecin et infirmier peuvent rechercher et consulter les dossiers ;
    l'écriture administrative est réservée à l'infirmier.
    """
    allowed_roles = [UserRole.MEDECIN, UserRole.INFIRMIER]