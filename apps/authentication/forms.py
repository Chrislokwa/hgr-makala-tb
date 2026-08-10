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


class UserAdminCreateForm(NoClientValidationMixin, forms.ModelForm):
    nom = forms.CharField(
        label="Nom",
        widget=forms.TextInput(attrs={'placeholder': 'ex. Kalombo'})
    )
    post_nom = forms.CharField(
        label="Post-nom",
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'ex. Kanyinda'})
    )
    prenom = forms.CharField(
        label="Prénom",
        widget=forms.TextInput(attrs={'placeholder': 'ex. Paul'})
    )
    email = forms.EmailField(
        label="Adresse e-mail",
        widget=forms.TextInput(attrs={'placeholder': 'prenom.nom@hgr-makala.cd'})
    )
    phone = forms.CharField(
        label="Téléphone",
        required=False,
        widget=forms.TextInput(attrs={'placeholder': '+243 8X XXX XXXX'})
    )
    role = forms.ChoiceField(
        label="Rôle",
        choices=UserRole.choices,
        widget=forms.Select()
    )

    class Meta:
        model = CustomUser
        fields = ['email', 'role', 'post_nom', 'phone']

    def clean(self):
        cleaned = super().clean()
        for name in ('nom', 'post_nom', 'prenom'):
            if cleaned.get(name):
                cleaned[name] = CustomUser.strip_name_prefix(cleaned[name])
        return cleaned

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if email and CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Cette adresse e-mail est déjà utilisée par un autre compte.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email'].strip().lower()
        user.first_name = self.cleaned_data.get('prenom', '').strip()
        user.post_nom = self.cleaned_data.get('post_nom', '').strip()
        user.last_name = self.cleaned_data.get('nom', '').strip()
        user.phone = self.cleaned_data.get('phone', '').strip() or None
        if commit:
            user.save()
        return user


class UserAdminUpdateForm(NoClientValidationMixin, forms.ModelForm):
    nom = forms.CharField(
        label="Nom",
        widget=forms.TextInput()
    )
    post_nom = forms.CharField(
        label="Post-nom",
        required=False,
        widget=forms.TextInput()
    )
    prenom = forms.CharField(
        label="Prénom",
        widget=forms.TextInput()
    )
    email = forms.EmailField(
        label="Adresse e-mail",
        widget=forms.TextInput()
    )
    phone = forms.CharField(
        label="Téléphone",
        required=False,
        widget=forms.TextInput()
    )

    class Meta:
        model = CustomUser
        fields = ['email', 'post_nom', 'phone']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['nom'].initial = self.instance.last_name
            self.fields['post_nom'].initial = self.instance.post_nom
            self.fields['prenom'].initial = self.instance.first_name
            self.fields['phone'].initial = self.instance.phone

    def clean(self):
        cleaned = super().clean()
        for name in ('nom', 'post_nom', 'prenom'):
            if cleaned.get(name):
                cleaned[name] = CustomUser.strip_name_prefix(cleaned[name])
        return cleaned

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if email and CustomUser.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Cette adresse e-mail est déjà utilisée par un autre compte.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email'].strip().lower()
        user.first_name = self.cleaned_data.get('prenom', '').strip()
        user.post_nom = self.cleaned_data.get('post_nom', '').strip()
        user.last_name = self.cleaned_data.get('nom', '').strip()
        user.phone = self.cleaned_data.get('phone', '').strip() or None
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
