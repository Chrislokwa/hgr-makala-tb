from django import forms
from django.utils import timezone

from apps.users.forms import NoClientValidationMixin

from .models import (
    ApparenceEchantillon,
    Consultation,
    DecisionDiagnostic,
    EpisodeTB,
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
    SiteMaladie,
    TechniqueColoration,
    TypeCasTraitement,
    TypeConsultation,
    TypeExamen,
    TypeModificationTraitement,
    TypePatient,
    VisiteSuivi,
)
from .services import CONTROLES_SUIVI


class DossierProvisoireForm(NoClientValidationMixin, forms.Form):
    """Formulaire de création d'un épisode de maladie TB (nouveau dossier).

    Section Patient : nom, post_nom, prenom, sexe, date_naissance,
    telephone, adresse (district/secteur/cellule/village).
    Section Épisode : type_patient, site_maladie, diagnostic.
    Les champs NDP, date_ouverture et statut sont générés automatiquement
    et affichés en texte brut dans le template.
    """

    # --- Champs Patient ---
    nom = forms.CharField(
        label='Nom',
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'ex. Kalombo'}),
    )
    post_nom = forms.CharField(
        label='Post-nom',
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
    telephone = forms.CharField(
        label='Téléphone',
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={'placeholder': '+243 8X XXX XXXX'}),
    )
    adresse = forms.CharField(
        label='Adresse',
        required=False,
        max_length=300,
        widget=forms.TextInput(attrs={'placeholder': 'ex. Av. Kasavubu 12, Q. Lingwala'}),
    )

    # --- Champs Épisode TB ---
    type_patient = forms.ChoiceField(
        label='Type de patient',
        choices=TypePatient.choices,
        widget=forms.RadioSelect(),
    )
    site_maladie = forms.ChoiceField(
        label='Site de la maladie',
        choices=SiteMaladie.choices,
        widget=forms.RadioSelect(),
    )
    diagnostic = forms.CharField(
        label='Diagnostic initial',
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Diagnostic initial du patient…',
            'rows': 3,
        }),
    )

    def clean_date_naissance(self):
        date = self.cleaned_data.get('date_naissance')
        if date and date > timezone.localdate():
            raise forms.ValidationError("La date de naissance ne peut pas être dans le futur.")
        return date

    def clean(self):
        cleaned = super().clean()
        adresse = (cleaned.get('adresse') or '').strip()
        if adresse:
            parts = [p.strip() for p in adresse.split(',') if p.strip()]
            if len(parts) >= 1:
                cleaned['district'] = parts[0]
            if len(parts) >= 2:
                cleaned['secteur'] = parts[1]
            if len(parts) >= 3:
                cleaned['cellule'] = parts[2]
            if len(parts) >= 4:
                cleaned['village'] = parts[3]
        else:
            cleaned['district'] = ''
            cleaned['secteur'] = ''
            cleaned['cellule'] = ''
            cleaned['village'] = ''
        cleaned.pop('adresse', None)
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


class ConsultationForm(NoClientValidationMixin, forms.Form):
    """Écran 2 — Formulaire de consultation médicale."""

    date_consultation = forms.DateField(
        label='Date de consultation',
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    type_consultation = forms.ChoiceField(
        label='Type de consultation',
        choices=TypeConsultation.choices,
        widget=forms.RadioSelect(),
    )
    motif_consultation = forms.CharField(
        label='Motif de consultation',
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Motif de la consultation…',
            'rows': 3,
        }),
    )
    plaintes = forms.CharField(
        label='Plaintes',
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Plaintes du patient…',
            'rows': 3,
        }),
    )
    symptomes = forms.CharField(
        label='Symptômes',
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Symptômes observés…',
            'rows': 3,
        }),
    )
    antecedents = forms.CharField(
        label='Antécédents',
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Antécédents médicaux…',
            'rows': 3,
        }),
    )
    comorbidites = forms.CharField(
        label='Comorbidités',
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Comorbidités identifiées…',
            'rows': 3,
        }),
    )
    poids = forms.DecimalField(
        label='Poids (kg)',
        required=False,
        min_value=0,
        max_value=300,
        decimal_places=1,
        widget=forms.NumberInput(attrs={'placeholder': 'ex. 55.5'}),
    )
    temperature = forms.DecimalField(
        label='Température (°C)',
        required=False,
        min_value=30,
        max_value=45,
        decimal_places=1,
        widget=forms.NumberInput(attrs={'placeholder': 'ex. 37.0'}),
    )
    frequence_cardiaque = forms.IntegerField(
        label='Fréq. cardiaque',
        required=False,
        min_value=30,
        max_value=250,
        widget=forms.NumberInput(attrs={'placeholder': 'ex. 72'}),
    )
    tension_arterielle = forms.CharField(
        label='Tension',
        required=False,
        max_length=10,
        widget=forms.TextInput(attrs={'placeholder': 'ex. 12/8'}),
    )
    diagnostic_initial = forms.CharField(
        label='Diagnostic initial',
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Diagnostic initial posé…',
            'rows': 3,
        }),
    )
    diagnostic_certitude = forms.CharField(
        label='Diagnostic de certitude',
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Diagnostic de certitude confirmé…',
            'rows': 3,
        }),
    )

    def clean_date_consultation(self):
        date = self.cleaned_data.get('date_consultation')
        if date and date > timezone.localdate():
            raise forms.ValidationError("La date de consultation ne peut pas être dans le futur.")
        return date