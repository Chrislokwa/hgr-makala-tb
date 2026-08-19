from django import forms
from django.utils import timezone

from apps.users.forms import NoClientValidationMixin

from .models import (
    ExamenPrescription,
    MoisControle,
    MotifExamen,
    NatureEchantillon,
    Patient,
    Sexe,
    StatutVihConnu,
    TypeExamen,
)


class DossierProvisoireForm(NoClientValidationMixin, forms.ModelForm):
    nom = forms.CharField(
        label='Nom de famille',
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'ex. Kalombo'}),
    )
    post_nom = forms.CharField(
        label='Post-nom',
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'ex. Kanyinda'}),
    )
    prenom = forms.CharField(
        label='Prénom',
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'ex. Paul'}),
    )
    sexe = forms.ChoiceField(
        label='Sexe',
        choices=Sexe.choices,
        widget=forms.RadioSelect(),
    )
    date_naissance = forms.DateField(
        label='Date de naissance',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    district = forms.CharField(
        label='District',
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'ex. Ngaliema'}),
    )
    secteur = forms.CharField(
        label='Secteur',
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'ex. Secteur Météo'}),
    )
    cellule = forms.CharField(
        label='Cellule',
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'ex. Cellule B'}),
    )
    village = forms.CharField(
        label='Village',
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'ex. Village Turc'}),
    )
    telephone = forms.CharField(
        label='Téléphone',
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={'placeholder': '+243 8X XXX XXXX'}),
    )
    poids = forms.DecimalField(
        label='Poids du patient (kg)',
        required=False,
        min_value=0,
        max_value=300,
        decimal_places=1,
        widget=forms.NumberInput(attrs={'placeholder': 'ex. 55.5'}),
    )
    autres_comorbidites = forms.CharField(
        label='Précisez (si « Autre » est coché)',
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'ex. Drépanocytose, insuffisance rénale…',
            'rows': 2,
        }),
    )
    observations_cliniques = forms.CharField(
        label='Observations cliniques complémentaires',
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Examen physique, signes cliniques, présence d’une cicatrice BCG…',
        }),
    )

    class Meta:
        model = Patient
        fields = [
            'nom', 'post_nom', 'prenom', 'sexe', 'date_naissance',
            'district', 'secteur', 'cellule', 'village', 'telephone',
            'poids',
            'signe_toux_persistante', 'signe_fievre_sueurs',
            'signe_perte_poids', 'signe_hemoptysie', 'signe_contact_cas_tpm',
            'comorb_vih', 'comorb_diabete', 'comorb_malnutrition',
            'comorb_autre', 'autres_comorbidites', 'observations_cliniques',
        ]
        labels = {
            'signe_toux_persistante': 'Toux persistante ≥ 2 semaines',
            'signe_fievre_sueurs': 'Fièvre et sueurs nocturnes',
            'signe_perte_poids': 'Perte de poids inexpliquée',
            'signe_hemoptysie': 'Hémoptysie (crachats striés de sang)',
            'signe_contact_cas_tpm': 'Contact étroit avec un cas TPM+',
            'comorb_vih': 'VIH/SIDA (connu)',
            'comorb_diabete': 'Diabète',
            'comorb_malnutrition': 'Malnutrition',
            'comorb_autre': 'Autre comorbidité',
        }

    def clean_date_naissance(self):
        date = self.cleaned_data.get('date_naissance')
        if date and date > timezone.localdate():
            raise forms.ValidationError("La date de naissance ne peut pas être dans le futur.")
        return date


class PrescriptionExamenForm(NoClientValidationMixin, forms.ModelForm):
    nature_echantillon = forms.ChoiceField(
        label='Nature de l’échantillon à prélever *',
        choices=NatureEchantillon.choices,
        widget=forms.Select(),
    )
    organe = forms.CharField(
        label='Précisez l’organe *',
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'ex. ganglion, plèvre, os…'}),
    )
    motif = forms.ChoiceField(
        label='Motif de l’examen *',
        choices=MotifExamen.choices,
        widget=forms.RadioSelect(),
    )
    mois_controle = forms.ChoiceField(
        label='Mois de contrôle *',
        required=False,
        choices=MoisControle.choices,
        widget=forms.Select(),
    )
    examens = forms.ModelMultipleChoiceField(
        label='Type(s) d’examen(s) à réaliser *',
        queryset=TypeExamen.objects.filter(actif=True),
        widget=forms.CheckboxSelectMultiple(),
        error_messages={'required': 'Sélectionnez au moins un type d’examen.'},
    )
    date_prelevement = forms.DateField(
        label='Date prévue du premier prélèvement',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    statut_vih = forms.ChoiceField(
        label='Statut VIH connu du patient (optionnel)',
        required=False,
        choices=[('', '— Non renseigné —')] + list(StatutVihConnu.choices),
        widget=forms.Select(),
    )
    observations = forms.CharField(
        label='Observations cliniques complémentaires',
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Recommandations spécifiques pour le laboratoire…',
        }),
    )

    class Meta:
        model = ExamenPrescription
        fields = [
            'nature_echantillon', 'organe', 'motif', 'mois_controle',
            'examens', 'date_prelevement', 'statut_vih', 'observations',
        ]

    def clean(self):
        cleaned = super().clean()
        nature = cleaned.get('nature_echantillon')
        organe = (cleaned.get('organe') or '').strip()
        if nature == NatureEchantillon.EXTRA_PULMONAIRE and not organe:
            self.add_error('organe', 'Précisez l’organe concerné pour un prélèvement extra-pulmonaire.')

        motif = cleaned.get('motif')
        mois_controle = cleaned.get('mois_controle')
        if motif == MotifExamen.SUIVI_CONTROLE and not mois_controle:
            self.add_error(
                'mois_controle',
                'Indiquez le mois de contrôle (C2, C3, C5, fin de traitement, etc.).',
            )

        examens = cleaned.get('examens')
        if examens:
            types_exigeant_culture = [e for e in examens if e.exige_culture]
            if types_exigeant_culture and not any(e.code == 'CULTURE' for e in examens):
                self.add_error(
                    'examens',
                    'Le test de sensibilité (DST) n’est possible que si la culture est également demandée.',
                )

        date_prelevement = cleaned.get('date_prelevement')
        if date_prelevement and date_prelevement < timezone.localdate():
            self.add_error(
                'date_prelevement',
                'La date de prélèvement ne peut pas être dans le passé.',
            )
        return cleaned