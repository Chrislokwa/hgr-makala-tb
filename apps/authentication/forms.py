from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, UserChangeForm
from .models import CustomUser, UserRole

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Identifiant",
        widget=forms.TextInput(attrs={
            'id': 'luser',
            'placeholder': 'ex. pkalombo',
            'autocomplete': 'username',
            'required': True,
        })
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={
            'id': 'lpass',
            'placeholder': '••••••',
            'autocomplete': 'current-password',
            'required': True,
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


class UserAdminCreateForm(forms.ModelForm):
    nom = forms.CharField(
        label="Nom complet",
        widget=forms.TextInput(attrs={'placeholder': 'ex. Inf. Claire Bofassa', 'required': True})
    )
    username = forms.CharField(
        label="Identifiant",
        widget=forms.TextInput(attrs={'placeholder': 'ex. cbofassa', 'required': True})
    )
    email = forms.EmailField(
        label="Adresse e-mail",
        required=False,
        widget=forms.EmailInput(attrs={'placeholder': 'prenom.nom@hgr-makala.cd'})
    )
    role = forms.ChoiceField(
        label="Rôle",
        choices=UserRole.choices,
        widget=forms.Select(attrs={'required': True})
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


class UserAdminUpdateForm(forms.ModelForm):
    nom = forms.CharField(
        label="Nom complet",
        widget=forms.TextInput(attrs={'required': True})
    )
    email = forms.EmailField(
        label="Adresse e-mail",
        required=False,
        widget=forms.EmailInput()
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
