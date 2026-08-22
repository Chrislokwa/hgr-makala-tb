from apps.users.permissions import RoleRequiredMixin
from apps.users.models import UserRole


class StatisticienRequiredMixin(RoleRequiredMixin):
    allowed_roles = [UserRole.STATISTICIEN, UserRole.ADMIN]
