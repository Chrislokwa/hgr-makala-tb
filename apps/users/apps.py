from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = 'apps.users'

    def ready(self):
        # Signaux d'audit : connexion / déconnexion
        try:
            from django.contrib.auth.signals import user_logged_in, user_logged_out
            from django.dispatch import receiver
            from .models import audit_log, AuditLog

            @receiver(user_logged_in)
            def _log_login(sender, request, user, **kwargs):
                audit_log(user, AuditLog.Action.LOGIN, f"Connexion de {user.titled_name} ({user.get_role_display()})", request=request)

            @receiver(user_logged_out)
            def _log_logout(sender, request, user, **kwargs):
                if user:
                    audit_log(user, AuditLog.Action.LOGOUT, f"Déconnexion de {user.titled_name}", request=request)
        except Exception:
            pass
