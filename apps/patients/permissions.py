from apps.users.models import UserRole
from apps.users.permissions import RoleRequiredMixin


class MedecinRequiredMixin(RoleRequiredMixin):
    allowed_roles = [UserRole.MEDECIN]