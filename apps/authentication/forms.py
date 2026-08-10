from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
    UserChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    PasswordChangeForm,
)
from .models import CustomUser, UserRole

class NoClientValidationMixin(forms.Form):
    use_required_attribute = False
    _html_restriction_attrs = ('maxlength', 'minlength', 'pattern', 'min', 'max', 'step')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            for attr in self._html_restriction_attrs:
                field.widget.attrs.pop(attr, None)


class CustomAuthenticationForm(NoClientValidationMixin, AuthenticationForm):

    username = forms.CharField(
        label="Identifiant",
        widget=forms.TextInput(attrs={
            'id': 'luser',
            'placeholder': 'ex. pkalombo',
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


class UserAdminCreateForm(NoClientValidationMixin, forms.ModelForm):
    nom = forms.CharField(
        label="Nom complet",
        widget=forms.TextInput(attrs={'placeholder': 'ex. Inf. Claire Bofassa'})
    )
    username = forms.CharField(
        label="Identifiant",
        widget=forms.TextInput(attrs={'placeholder': 'ex. cbofassa'})
    )
    email = forms.EmailField(
        label="Adresse e-mail",
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'prenom.nom@hgr-makala.cd'})
    )
    role = forms.ChoiceField(
        label="Rôle",
        choices=UserRole.choices,
        widget=forms.Select()
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'role']

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip().lower()
        if CustomUser.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Cet identifiant est déjà utilisé.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if email and CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Cette adresse e-mail est déjà utilisée par un autre compte.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        nom = self.cleaned_data.get('nom', '').strip()
        parts = nom.split(' ', 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''
        if commit:
            user.save()
        return user


class UserAdminUpdateForm(NoClientValidationMixin, forms.ModelForm):
    nom = forms.CharField(
        label="Nom complet",
        widget=forms.TextInput()
    )
    email = forms.EmailField(
        label="Adresse e-mail",
        required=False,
        widget=forms.TextInput()
    )

    class Meta:
        model = CustomUser
        fields = ['email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['nom'].initial = self.instance.display_name

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if email and CustomUser.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Cette adresse e-mail est déjà utilisée par un autre compte.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        nom = self.cleaned_data.get('nom', '').strip()
        parts = nom.split(' ', 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''
        if commit:
            user.save()
        return user


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
