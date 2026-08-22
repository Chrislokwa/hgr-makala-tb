from django.urls import path, reverse_lazy
from django.contrib.auth.views import (
    LogoutView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
    PasswordChangeView
)
from django.views.generic import RedirectView
from .views import (
    CustomLoginView,
    DashboardView,
)
from .forms import CustomPasswordResetForm, CustomSetPasswordForm, CustomPasswordChangeForm

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='login', permanent=False)),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('notification/', DashboardView.as_view(), name='notification'),

    # Phase 2 & 3 : Réinitialisation mot de passe
    path('password-reset/', PasswordResetView.as_view(
        template_name='authentication/password_reset.html',
        email_template_name='authentication/password_reset_email.html',
        subject_template_name='authentication/password_reset_subject.txt',
        success_url=reverse_lazy('password_reset_done'),
        form_class=CustomPasswordResetForm,
    ), name='password_reset'),
    path('password-reset/done/', PasswordResetDoneView.as_view(
        template_name='authentication/password_reset_done.html'
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', PasswordResetConfirmView.as_view(
        template_name='authentication/password_reset_confirm.html',
        success_url=reverse_lazy('password_reset_complete'),
        form_class=CustomSetPasswordForm,
    ), name='password_reset_confirm'),
    # Ancien chemin conserve pour compatibilite (evite 404 sur anciens e-mails)
    path('password-reset/confirm/<uidb64>/<token>/', PasswordResetConfirmView.as_view(
        template_name='authentication/password_reset_confirm.html',
        success_url=reverse_lazy('password_reset_complete'),
        form_class=CustomSetPasswordForm,
    ), name='password_reset_confirm_legacy'),
    path('password-reset/complete/', PasswordResetCompleteView.as_view(
        template_name='authentication/password_reset_complete.html'
    ), name='password_reset_complete'),

    # Phase 4.6 : Modification mot de passe
    path('password-change/', PasswordChangeView.as_view(
        template_name='authentication/password_change.html',
        success_url=reverse_lazy('notification'),
        form_class=CustomPasswordChangeForm,
    ), name='password_change'),
]
