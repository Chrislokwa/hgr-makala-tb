from django import forms
from django.utils import timezone

from apps.users.forms import NoClientValidationMixin

from .models import (
    ApparenceEchantillon,
    DecisionDiagnostic,
    ExamenPrescription,
    IssueFinale,
    ModeObservation,
    MoisControle,
    MotifExamen,
    NatureEchantillon,
    Patient,
    RendezVous,
    ResultatBacilloscopie,
    ResultatGeneXpert,
    ResultatLabo,
    SchemaTraitement,
    Sexe,
    TechniqueColoration,
    TypeCasTraitement,
    TypeExamen,
    TypeModificationTraitement,
    VisiteSuivi,
)
from .services import CONTROLES_SUIVI


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
    type_cas = forms.ChoiceField(
        label='Type de cas *',
        choices=TypeCasTraitement.choices,
        widget=forms.RadioSelect(),
    )
    date_debut = forms.DateField(
        label='Date de début du traitement *',
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    unite_traitement = forms.CharField(
        label='Unité de traitement',
        max_length=120,
        initial='HGR Makala',
        widget=forms.TextInput(attrs={'placeholder': 'ex. TS Makala, HGR Makala…'}),
    )
    notes_traitement = forms.CharField(
        label='Notes sur le traitement',
        required=False,
        widget=forms.Textarea(attrs={'rows': 2}),
    )

    class Meta:
        model = Patient
        fields = [
            'nom', 'post_nom', 'prenom', 'sexe', 'date_naissance',
            'district', 'secteur', 'cellule', 'village', 'telephone',
            'poids',
            'signe_toux_persistante', 'signe_fievre_sueurs',
            'signe_perte_poids', 'signe_hemoptysie', 'signe_contact_cas_tpm',
            'comorb_diabete', 'comorb_malnutrition',
            'comorb_autre', 'autres_comorbidites', 'observations_cliniques',
        ]
        labels = {
            'signe_toux_persistante': 'Toux persistante ≥ 2 semaines',
            'signe_fievre_sueurs': 'Fièvre et sueurs nocturnes',
            'signe_perte_poids': 'Perte de poids inexpliquée',
            'signe_hemoptysie': 'Hémoptysie (crachats striés de sang)',
            'signe_contact_cas_tpm': 'Contact étroit avec un cas TPM+',
            'comorb_diabete': 'Diabète',
            'comorb_malnutrition': 'Malnutrition',
            'comorb_autre': 'Autre comorbidité',
        }

    def clean_date_naissance(self):
        date = self.cleaned_data.get('date_naissance')
        if date and date > timezone.localdate():
            raise forms.ValidationError("La date de naissance ne peut pas être dans le futur.")
        return date

    def clean_date_debut(self):
        date_val = self.cleaned_data.get('date_debut')
        if date_val and date_val > timezone.localdate():
            raise forms.ValidationError("La date de début ne peut pas être dans le futur.")
        return date_val

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('comorb_autre') and not (cleaned.get('autres_comorbidites') or '').strip():
            self.add_error('autres_comorbidites', 'Précisez la comorbidité lorsque « Autre » est coché.')
        if not cleaned.get('comorb_autre'):
            cleaned['autres_comorbidites'] = ''
        return cleaned


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
            'examens', 'date_prelevement', 'observations',
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


class SaisieResultatForm(NoClientValidationMixin, forms.ModelForm):
    date_reception = forms.DateField(
        label='Date de réception de l’échantillon *',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    apparence = forms.ChoiceField(
        label='Apparence macroscopique de l’échantillon *',
        choices=ApparenceEchantillon.choices,
        widget=forms.Select(),
    )
    echantillon_1 = forms.ChoiceField(
        label='Échantillon 1 — jour J *',
        choices=ResultatBacilloscopie.choices,
        widget=forms.RadioSelect(),
    )
    echantillon_2 = forms.ChoiceField(
        label='Échantillon 2 — matin du lendemain *',
        choices=ResultatBacilloscopie.choices,
        widget=forms.RadioSelect(),
    )
    technique_coloration = forms.ChoiceField(
        label='Technique de coloration utilisée *',
        choices=TechniqueColoration.choices,
        widget=forms.RadioSelect(),
    )
    resultat_genexpert = forms.ChoiceField(
        label='Résultat GeneXpert *',
        choices=ResultatGeneXpert.choices,
        widget=forms.Select(),
    )
    commentaires = forms.CharField(
        label='Anomalies, observations et remarques',
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Échantillon contaminé, qualité insuffisante, remarques…',
            'rows': 3,
        }),
    )

    class Meta:
        model = ResultatLabo
        fields = [
            'date_reception', 'apparence',
            'echantillon_1', 'echantillon_2', 'technique_coloration',
            'resultat_genexpert', 'commentaires',
        ]

    def __init__(self, *args, prescription=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.prescription = prescription
        if prescription is None:
            return
        codes = set(
            prescription.examens.values_list('code', flat=True)
        )
        if 'BACILLOSCOPIE' not in codes:
            for champ in ('date_reception', 'apparence', 'echantillon_1',
                          'echantillon_2', 'technique_coloration'):
                self.fields.pop(champ)
        if 'GENEXPERT' not in codes:
            self.fields.pop('resultat_genexpert')

    def clean_date_reception(self):
        date = self.cleaned_data.get('date_reception')
        if date and date > timezone.localdate():
            raise forms.ValidationError(
                "La date de réception ne peut pas être dans le futur."
            )
        return date


class InterpretationForm(NoClientValidationMixin, forms.Form):
    interpretation = forms.CharField(
        label='Interprétation médicale *',
        widget=forms.Textarea(attrs={
            'placeholder': (
                'Analyse des données cliniques : évolution de la toux, bacilloscopie, '
                'GeneXpert, culture… et avis posé sur le diagnostic.'
            ),
            'rows': 5,
        }),
        error_messages={'required': 'Rédigez votre interprétation médicale.'},
    )
    observations = forms.CharField(
        label='Observations complémentaires',
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Éléments cliniques complémentaires pris en compte…',
            'rows': 3,
        }),
    )
    decision = forms.ChoiceField(
        label='Décision de diagnostic',
        choices=DecisionDiagnostic.choices,
        widget=forms.RadioSelect(),
        error_messages={'required': 'Choisissez l’issue du diagnostic.'},
    )


class InformationsAdministrativesForm(NoClientValidationMixin, forms.ModelForm):
    """US3.1 / UC1 et US3.2 / UC2 — Formulaire administratif du patient."""

    nom = forms.CharField(
        label='Nom de famille *',
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
        label='Prénom *',
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'ex. Paul'}),
    )
    sexe = forms.ChoiceField(
        label='Sexe *',
        choices=Sexe.choices,
        widget=forms.RadioSelect(),
    )
    date_naissance = forms.DateField(
        label='Date de naissance *',
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

    CHAMPS_OBLIGATOIRES = ('nom', 'prenom', 'sexe', 'date_naissance')

    class Meta:
        model = Patient
        fields = [
            'nom', 'post_nom', 'prenom', 'sexe', 'date_naissance',
            'district', 'secteur', 'cellule', 'village', 'telephone',
        ]

    def clean_date_naissance(self):
        date = self.cleaned_data.get('date_naissance')
        if date and date > timezone.localdate():
            raise forms.ValidationError(
                "La date de naissance ne peut pas être dans le futur."
            )
        return date


# ---------------------------------------------------------------------------
# Epic 4 — Suivi thérapeutique (US4.1, US4.2, US4.3)
# ---------------------------------------------------------------------------


class ObservanceMoisForm(forms.Form):
    """US4.1 — Grille d'observance d'un mois (jours 1 à 31, codes X/-/O/↑)."""

    def __init__(self, *args, traitement=None, mois=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.traitement = traitement
        self.mois = mois
        total_mois = traitement.schema.duree_totale_mois if traitement else 6
        self.fields['mois'] = forms.ChoiceField(
            label='Mois de traitement',
            choices=[(m, f'Mois {m}') for m in range(1, total_mois + 1)],
            initial=mois,
            widget=forms.Select(attrs={'data-auto-submit': 'month'}),
        )
        existantes = {}
        if traitement is not None:
            existantes = {
                observation.jour: observation.statut
                for observation in traitement.observances.filter(mois=mois)
            }
        for jour in range(1, 32):
            self.fields[f'jour_{jour}'] = forms.ChoiceField(
                label=str(jour),
                required=False,
                choices=[('', '—')] + list(ModeObservation.choices),
                initial=existantes.get(jour, ''),
                widget=forms.Select(attrs={'class': 'obs-sel'}),
            )

    @property
    def statuts_par_jour(self):
        donnees = {champ: valeur for champ, valeur in self.cleaned_data.items() if champ.startswith('jour_')}
        return {champ.replace('jour_', ''): (valeur or '') for champ, valeur in donnees.items()}


class VisiteSuiviForm(NoClientValidationMixin, forms.ModelForm):
    """US4.1 — Visite de contrôle clinique (poids actuel, signes d'alerte)."""

    class Meta:
        model = VisiteSuivi
        fields = [
            'date', 'poids',
            'troubles_visuels', 'jaunisse', 'eruption_cutanee', 'vertiges',
            'autres_effets', 'observations',
        ]
        labels = {
            'date': 'Date de la visite *',
            'poids': 'Poids actuel (kg)',
            'troubles_visuels': 'Troubles visuels (ethambutol)',
            'jaunisse': 'Jaunisse / ictère',
            'eruption_cutanee': 'Éruptions cutanées',
            'vertiges': 'Vertiges',
            'autres_effets': 'Autres effets indésirables',
            'observations': 'Observations cliniques',
        }
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'poids': forms.NumberInput(attrs={'placeholder': 'ex. 56.0'}),
            'autres_effets': forms.Textarea(attrs={'rows': 2}),
            'observations': forms.Textarea(attrs={'rows': 2}),
        }

    def clean_date(self):
        date_val = self.cleaned_data.get('date')
        if date_val and date_val > timezone.localdate():
            raise forms.ValidationError("La date de visite ne peut pas être dans le futur.")
        return date_val


class ModifierTraitementForm(NoClientValidationMixin, forms.Form):
    """US4.1 — Modification du traitement par le médecin (motif obligatoire)."""

    type_modification = forms.ChoiceField(
        label='Type de modification *',
        choices=TypeModificationTraitement.choices,
        widget=forms.RadioSelect(),
    )
    motif_medical = forms.CharField(
        label='Motif médical *',
        widget=forms.Textarea(attrs={
            'placeholder': 'Raison clinique de la modification (obligatoire)…',
            'rows': 3,
        }),
        error_messages={'required': 'Le motif médical est obligatoire.'},
    )
    nouveau_schema = forms.ModelChoiceField(
        label='Schéma de retraitement (Catégorie II)',
        required=False,
        queryset=SchemaTraitement.objects.filter(categorie='RETRAITEMENT', actif=True),
        widget=forms.Select(),
        help_text="Appliqué automatiquement lors du passage en Catégorie II.",
    )
    medicament_suspendu = forms.CharField(
        label='Médicament suspendu',
        required=False,
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': 'ex. EH, S…'}),
    )
    nouvelle_posologie_jour = forms.IntegerField(
        label='Nouvelle posologie (comprimés/jour)',
        required=False,
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={'placeholder': 'ex. 4'}),
    )
    description = forms.CharField(
        label='Précisions complémentaires',
        required=False,
        widget=forms.Textarea(attrs={'rows': 2}),
    )


class BonControleForm(NoClientValidationMixin, forms.Form):
    """US4.2 — Bon de demande d'examen de laboratoire de contrôle."""

    mois_controle = forms.ChoiceField(
        label='Mois de contrôle *',
        choices=[(valeur, libelle) for valeur, libelle in MoisControle.choices if valeur in CONTROLES_SUIVI],
        widget=forms.Select(),
    )
    examens = forms.ModelMultipleChoiceField(
        label='Examen(s) à réaliser *',
        queryset=TypeExamen.objects.filter(actif=True),
        widget=forms.CheckboxSelectMultiple(),
        error_messages={'required': 'Sélectionnez au moins un examen.'},
    )
    observations_cliniques = forms.CharField(
        label='Observations cliniques',
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Évolution clinique, éventuels effets indésirables…',
            'rows': 2,
        }),
    )

    EXAMENS_PAR_DEFAUT = ('BACILLOSCOPIE', 'GENEXPERT', 'CULTURE')

    def __init__(self, *args, patient=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.patient = patient
        if patient is not None and not self.is_bound:
            defauts = [e.pk for e in TypeExamen.objects.filter(code__in=self.EXAMENS_PAR_DEFAUT)]
            self.fields['examens'].initial = defauts

    def clean_mois_controle(self):
        mois_controle = self.cleaned_data.get('mois_controle')
        if mois_controle not in CONTROLES_SUIVI:
            raise forms.ValidationError("Mois de contrôle invalide.")
        return mois_controle


class RendezVousForm(NoClientValidationMixin, forms.ModelForm):
    """US4.3 — Planification d'un rendez-vous sur la carte du malade."""

    class Meta:
        model = RendezVous
        fields = ['date', 'heure', 'type', 'motif']
        labels = {
            'date': 'Date *',
            'heure': 'Heure *',
            'type': 'Type de rendez-vous *',
            'motif': 'Motif / précision',
        }
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'heure': forms.TimeInput(attrs={'type': 'time'}),
            'motif': forms.TextInput(attrs={'placeholder': 'ex. contrôle mensuel, remise de médicaments…'}),
        }

    def clean_date(self):
        date_val = self.cleaned_data.get('date')
        if date_val and date_val < timezone.localdate():
            raise forms.ValidationError("La date du rendez-vous ne peut pas être dans le passé.")
        return date_val


class CloturerTraitementForm(NoClientValidationMixin, forms.Form):
    """Registre de cas — Issue finale et clôture du dossier."""

    issue_finale = forms.ChoiceField(
        label='Issue finale *',
        choices=IssueFinale.choices,
        widget=forms.RadioSelect(),
        error_messages={'required': 'Choisissez l’issue finale du traitement.'},
    )
    date_issue = forms.DateField(
        label='Date de l’issue *',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields['date_issue'].initial = timezone.localdate()