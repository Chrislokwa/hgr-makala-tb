from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    PasswordChangeForm,
)
from apps.users.models import CustomUser
from apps.users.forms import NoClientValidationMixin

class CustomAuthenticationForm(NoClientValidationMixin, AuthenticationForm):

    username = forms.CharField(
        label="Adresse e-mail",
        widget=forms.TextInput(attrs={
            'id': 'luser',
            'placeholder': 'prenom.nom@hgr-makala.cd',
            'autocomplete': 'username',
        })
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={
            'id': 'lpass',
            'placeholder': '••••••',
            'autocomplete': 'current-password',
        })
    )

    error_messages = {
        'invalid_login': "Identifiants incorrects.",
        'inactive': "Ce compte a été désactivé. Contactez votre administrateur.",
    }

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            user_obj = CustomUser.objects.filter(username__iexact=username).first()
            if user_obj and user_obj.check_password(password):
                if not user_obj.is_active:
                    raise forms.ValidationError(
                        self.error_messages['inactive'],
                        code='inactive',
                    )
                self.user_cache = user_obj
            else:
                raise self.get_invalid_login_error()

        return self.cleaned_data


class CustomPasswordResetForm(NoClientValidationMixin, PasswordResetForm):
    email = forms.EmailField(
        label="Adresse e-mail",
        max_length=254,
        widget=forms.TextInput(attrs={"autocomplete": "email"}),
    )


class CustomSetPasswordForm(NoClientValidationMixin, SetPasswordForm):
    pass


class CustomPasswordChangeForm(NoClientValidationMixin, PasswordChangeForm):
    pass
