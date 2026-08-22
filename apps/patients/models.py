# pyrefly: ignore [missing-import]
from django.conf import settings
# pyrefly: ignore [missing-import]
from django.db import models
from django.utils import timezone


class Sexe(models.TextChoices):
    MASCULIN = 'M', 'Masculin'
    FEMININ = 'F', 'Féminin'


class StatutDossier(models.TextChoices):
    PROVISOIRE = 'PROVISOIRE', 'Provisoire'
    EN_TRAITEMENT = 'EN_TRAITEMENT', 'En traitement'
    GUERI = 'GUERI', 'Guéri'
    CLOTURE = 'CLOTURE', 'Clôturé'


class Patient(models.Model):
    ndp = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Numéro de dossier patient, généré automatiquement (NDP-AAAA-NNNN).",
    )
    nom = models.CharField(max_length=100, db_index=True)
    post_nom = models.CharField(max_length=100, blank=True)
    prenom = models.CharField(max_length=100, db_index=True)
    sexe = models.CharField(max_length=1, choices=Sexe.choices)
    date_naissance = models.DateField(db_index=True)

    district = models.CharField(max_length=100, blank=True)
    secteur = models.CharField(max_length=100, blank=True)
    cellule = models.CharField(max_length=100, blank=True)
    village = models.CharField(max_length=100, blank=True)
    telephone = models.CharField(max_length=20, blank=True)

    poids = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Poids du patient en kg, nécessaire au calcul de la posologie.",
    )
    signe_toux_persistante = models.BooleanField(default=False)
    signe_fievre_sueurs = models.BooleanField(default=False)
    signe_perte_poids = models.BooleanField(default=False)
    signe_hemoptysie = models.BooleanField(default=False)
    signe_contact_cas_tpm = models.BooleanField(default=False)
    comorb_diabete = models.BooleanField(default=False)
    comorb_malnutrition = models.BooleanField(default=False)
    comorb_autre = models.BooleanField(default=False)
    autres_comorbidites = models.TextField(blank=True)
    observations_cliniques = models.TextField(blank=True)

    statut = models.CharField(
        max_length=20,
        choices=StatutDossier.choices,
        default=StatutDossier.PROVISOIRE,
    )
    cree_le = models.DateTimeField(auto_now_add=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='patients_crees',
        help_text="Médecin à l'origine de la création du dossier.",
    )

    # --- EPIC 3 : admission administrative définitive (US3.1 / UC1) ---
    date_admission = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de finalisation de l'admission administrative par l'infirmier.",
    )
    admise_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='admissions_finalisees',
        help_text="Infirmier ayant finalisé l'admission administrative.",
    )

    class Meta:
        ordering = ['-cree_le']

    @classmethod
    def generer_ndp(cls):
        annee = timezone.localdate().year
        prefix = f'NDP-{annee}-'
        dernier = (
            cls.objects
            .filter(ndp__startswith=prefix)
            .order_by('-ndp')
            .values_list('ndp', flat=True)
            .first()
        )
        sequence = (int(dernier.rsplit('-', 1)[1]) if dernier else 0) + 1
        return f'{prefix}{sequence:04d}'

    @classmethod
    def trouver_doublon(cls, nom, prenom, date_naissance, exclure=None):
        queryset = cls.objects.filter(
            nom__iexact=nom,
            prenom__iexact=prenom,
            date_naissance=date_naissance,
        ).exclude(statut=StatutDossier.CLOTURE)
        if exclure is not None:
            queryset = queryset.exclude(pk=exclure.pk)
        return queryset.order_by('-cree_le').first()

    def save(self, *args, **kwargs):
        if not self.ndp:
            self.ndp = self.generer_ndp()
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return " ".join(
            part for part in (self.prenom, self.post_nom, self.nom) if part
        ).strip()

    @property
    def admission_finalisee(self):
        return self.date_admission is not None

    @property
    def age(self):
        if not self.date_naissance:
            return None
        aujourd_hui = timezone.localdate()
        return (
            aujourd_hui.year
            - self.date_naissance.year
            - ((aujourd_hui.month, aujourd_hui.day) < (self.date_naissance.month, self.date_naissance.day))
        )

    @property
    def adresse_complete(self):
        return ", ".join(
            part for part in (self.district, self.secteur, self.cellule, self.village) if part
        ).strip()

    @property
    def signes_presents(self):
        libelles = {
            'signe_toux_persistante': 'Toux persistante ≥ 2 semaines',
            'signe_fievre_sueurs': 'Fièvre et sueurs nocturnes',
            'signe_perte_poids': 'Perte de poids inexpliquée',
            'signe_hemoptysie': 'Hémoptysie (crachats striés de sang)',
            'signe_contact_cas_tpm': 'Contact étroit avec un cas TPM+',
        }
        return [libelle for champ, libelle in libelles.items() if getattr(self, champ)]

    @property
    def comorbidites_presentes(self):
        libelles = {
            'comorb_diabete': 'Diabète',
            'comorb_malnutrition': 'Malnutrition',
            'comorb_autre': 'Autre',
        }
        resultat = [libelle for champ, libelle in libelles.items() if getattr(self, champ)]
        if 'Autre' in resultat and self.autres_comorbidites:
            resultat[-1] = f"Autre ({self.autres_comorbidites})"
        return resultat

    @property
    def initiales(self):
        parties = [part for part in (self.prenom, self.nom) if part]
        if len(parties) >= 2:
            return f"{parties[0][0]}{parties[1][0]}".upper()
        if parties and parties[0]:
            return parties[0][:2].upper()
        return '?'

    @property
    def avatar_palette(self):
        palettes = [
            ('#dbe7f3', '#375a83'),
            ('#e3efe4', '#2f6b46'),
            ('#f3e9d8', '#7d5a17'),
            ('#ece4f2', '#5f4b8b'),
            ('#f5e3e0', '#9a4632'),
            ('#e0efee', '#2a6f6f'),
        ]
        h = 0
        for char in self.full_name:
            h = (h * 31 + ord(char)) % 997
        return palettes[h % len(palettes)]

    @property
    def avatar_style(self):
        fond, texte = self.avatar_palette
        return f"--av:{fond};--avt:{texte}"

    def __str__(self):
        return f"{self.ndp} · {self.full_name}"


class TypeExamen(models.Model):
    code = models.CharField(max_length=30, unique=True)
    libelle = models.CharField(max_length=120)
    description = models.CharField(max_length=200, blank=True)
    nb_echantillons = models.PositiveSmallIntegerField(default=1)
    exige_culture = models.BooleanField(
        default=False,
        help_text="Ce type d'examen ne peut être prescrit que si la culture est également demandée.",
    )
    actif = models.BooleanField(default=True)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['ordre']

    def __str__(self):
        return self.libelle


class NatureEchantillon(models.TextChoices):
    PULMONAIRE = 'P', 'Pulmonaire (P)'
    EXTRA_PULMONAIRE = 'EP', 'Extra-pulmonaire (EP)'


class MotifExamen(models.TextChoices):
    DIAGNOSTIC = 'DIAGNOSTIC', 'Diagnostic'
    SUIVI_CONTROLE = 'SUIVI', 'Suivi / Contrôle'


class MoisControle(models.TextChoices):
    C1 = 'C1', 'C1 (1er mois)'
    C2 = 'C2', 'C2 (2e mois)'
    C3 = 'C3', 'C3 (3e mois)'
    C4 = 'C4', 'C4 (4e mois)'
    C5 = 'C5', 'C5 (5e mois)'
    C6 = 'C6', 'C6 (6e mois)'
    FIN = 'FIN', 'Fin de traitement'


class StatutExamen(models.TextChoices):
    EN_ATTENTE = 'EN_ATTENTE', 'En attente'
    RESULTATS_DISPONIBLES = 'RESULTATS_DISPONIBLES', 'Disponible'


class ApparenceEchantillon(models.TextChoices):
    MUCOPURULENT = 'MUCOPURULENT', 'Mucopurulent'
    SALIVE = 'SALIVE', 'Salive'
    SANG = 'SANG', 'Sang'


class ResultatBacilloscopie(models.TextChoices):
    NEGATIF = 'NEG', 'Nég'
    BAAR_1_9 = '1_9', '1-9 BAAR'
    POSITIF_1 = '+', '+'
    POSITIF_2 = '++', '++'
    POSITIF_3 = '+++', '+++'


class TechniqueColoration(models.TextChoices):
    ZN = 'ZN', 'ZN — Ziehl-Neelsen'
    LED = 'LED', 'LED — Microscopie à fluorescence'


class ResultatGeneXpert(models.TextChoices):
    MTB_PLUS_RIF_PLUS = 'MTB_PLUS_RIF_PLUS', 'MTB+ RIF+'
    MTB_PLUS_RIF_MOINS = 'MTB_PLUS_RIF_MOINS', 'MTB+ RIF-'
    MTB_MOINS_RIF_PLUS = 'MTB_MOINS_RIF_PLUS', 'MTB- RIF+'
    INVALID = 'INVALID', 'Invalid'
    NON_FAIT = 'NON_FAIT', 'Non fait'


class StatutResultat(models.TextChoices):
    BROUILLON = 'BROUILLON', 'Brouillon'
    VALIDE = 'VALIDE', 'Validé'


class DecisionDiagnostic(models.TextChoices):
    CONFIRMEE = 'CONFIRMEE', 'Tuberculose confirmée'
    INFIRMEE = 'INFIRMEE', 'Tuberculose infirmée'


class ExamenPrescription(models.Model):
    numero_demande = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Numéro de demande unique (DM-AAAA-NNNN), généré automatiquement.",
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name='examens_prescrits',
    )
    medecin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='demandes_examens',
        help_text="Médecin prescripteur (horodaté lors de la validation).",
    )
    date_prescription = models.DateTimeField(auto_now_add=True, db_index=True)
    nature_echantillon = models.CharField(max_length=2, choices=NatureEchantillon.choices)
    organe = models.CharField(
        max_length=100,
        blank=True,
        help_text="Organe concerné lorsque l'échantillon est extra-pulmonaire.",
    )
    motif = models.CharField(max_length=20, choices=MotifExamen.choices)
    mois_controle = models.CharField(
        max_length=10,
        choices=MoisControle.choices,
        blank=True,
        help_text="Mois de contrôle à effectuer, pour les examens de suivi.",
    )
    examens = models.ManyToManyField(TypeExamen, related_name='prescriptions')
    date_prelevement = models.DateField()
    observations = models.TextField(
        blank=True,
        help_text="Recommandations spécifiques à l'attention du laboratoire.",
    )
    statut = models.CharField(
        max_length=30,
        choices=StatutExamen.choices,
        default=StatutExamen.EN_ATTENTE,
    )

    class Meta:
        ordering = ['-date_prescription']

    def __str__(self):
        return f"{self.numero_demande} · {self.patient.full_name}"

    @property
    def types_libelles(self):
        return ' / '.join(
            examen.libelle for examen in self.examens.all().order_by('ordre')
        )

    @classmethod
    def generer_numero_demande(cls):
        annee = timezone.localdate().year
        prefix = f'DM-{annee}-'
        dernier = (
            cls.objects
            .filter(numero_demande__startswith=prefix)
            .order_by('-numero_demande')
            .values_list('numero_demande', flat=True)
            .first()
        )
        sequence = (int(dernier.rsplit('-', 1)[1]) if dernier else 0) + 1
        return f'{prefix}{sequence:04d}'

    def save(self, *args, **kwargs):
        if not self.numero_demande:
            self.numero_demande = self.generer_numero_demande()
        super().save(*args, **kwargs)

    @property
    def resultat_recent(self):
        return self.resultats_labo.order_by('-cree_le').first()

    @property
    def resultat_valide(self):
        return (
            self.resultats_labo
            .filter(statut=StatutResultat.VALIDE)
            .order_by('-cree_le')
            .first()
        )

    @property
    def interpretation(self):
        return self.interpretations.order_by('-cree_le').first()


class ResultatLabo(models.Model):
    BAAR_POSITIFS = (ResultatBacilloscopie.BAAR_1_9, ResultatBacilloscopie.POSITIF_1,
                     ResultatBacilloscopie.POSITIF_2, ResultatBacilloscopie.POSITIF_3)

    prescription = models.ForeignKey(
        ExamenPrescription,
        on_delete=models.PROTECT,
        related_name='resultats_labo',
    )
    laborantin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='resultats_saisis',
        help_text="Laborantin ayant saisi les résultats.",
    )
    cree_le = models.DateTimeField(auto_now_add=True, db_index=True)
    date_lecture = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date et heure de lecture des lames (renseignées à la validation).",
    )
    statut = models.CharField(
        max_length=20,
        choices=StatutResultat.choices,
        default=StatutResultat.VALIDE,
    )
    date_reception = models.DateField(
        null=True,
        blank=True,
        help_text="Date de réception de l'échantillon au laboratoire.",
    )
    apparence = models.CharField(
        max_length=20,
        choices=ApparenceEchantillon.choices,
        blank=True,
        help_text="Apparence macroscopique de l'échantillon.",
    )
    echantillon_1 = models.CharField(
        max_length=8,
        choices=ResultatBacilloscopie.choices,
        blank=True,
        help_text="Résultat de l'échantillon 1 (prélevé le jour J).",
    )
    echantillon_2 = models.CharField(
        max_length=8,
        choices=ResultatBacilloscopie.choices,
        blank=True,
        help_text="Résultat de l'échantillon 2 (prélevé le lendemain matin).",
    )
    technique_coloration = models.CharField(
        max_length=10,
        choices=TechniqueColoration.choices,
        blank=True,
        help_text="Technique de coloration utilisée pour la bacilloscopie.",
    )
    resultat_genexpert = models.CharField(
        max_length=30,
        choices=ResultatGeneXpert.choices,
        blank=True,
    )
    commentaires = models.TextField(
        blank=True,
        help_text="Anomalies et remarques du laborantin (échantillon contaminé, qualité insuffisante…).",
    )

    class Meta:
        ordering = ['-cree_le']
        constraints = [
            models.UniqueConstraint(
                fields=['prescription', 'cree_le'],
                name='unique_resultat_labo_prescription_horodatage',
            ),
        ]

    def __str__(self):
        return f"{self.prescription.numero_demande} · {self.get_statut_display()}"

    @property
    def resultats_positifs(self):
        positifs = []
        if self.echantillon_1 in self.BAAR_POSITIFS:
            positifs.append(f"Échantillon 1 : {self.get_echantillon_1_display()}")
        if self.echantillon_2 in self.BAAR_POSITIFS:
            positifs.append(f"Échantillon 2 : {self.get_echantillon_2_display()}")
        if self.resultat_genexpert in (
                ResultatGeneXpert.MTB_PLUS_RIF_PLUS,
                ResultatGeneXpert.MTB_PLUS_RIF_MOINS,
                ResultatGeneXpert.MTB_MOINS_RIF_PLUS,
        ):
            positifs.append(f"GeneXpert : {self.get_resultat_genexpert_display()}")
        return positifs


class InterpretationResultat(models.Model):
    """Analyse médicale par le médecin traitant des résultats validés.

    La décision de diagnostic (confirmée / infirmée) est conservée au
    dossier ; elle ne modifie plus le statut du patient, l'admission
    étant validée par l'infirmier.
    """

    prescription = models.ForeignKey(
        ExamenPrescription,
        on_delete=models.PROTECT,
        related_name='interpretations',
        help_text="Demande d'examen dont les résultats sont interprétés.",
    )
    medecin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='interpretations_resultats',
        help_text="Médecin ayant analysé et interprété les résultats.",
    )
    cree_le = models.DateTimeField(auto_now_add=True, db_index=True)
    observations = models.TextField(
        blank=True,
        help_text="Analyse des données cliniques et des résultats de laboratoire.",
    )
    interpretation = models.TextField(
        help_text="Interprétation médicale des résultats et avis posé.",
    )
    decision = models.CharField(
        max_length=20,
        choices=DecisionDiagnostic.choices,
        help_text="Décision de diagnostic (point d'extension « Décision de diagnostic »).",
    )

    class Meta:
        ordering = ['-cree_le']
        constraints = [
            models.UniqueConstraint(
                fields=['prescription'],
                name='unique_interpretation_par_prescription',
            ),
        ]

    def __str__(self):
        return f"{self.prescription.numero_demande} · {self.get_decision_display()}"

    @property
    def patient(self):
        return self.prescription.patient


class Notification(models.Model):
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    message = models.CharField(max_length=255)
    url = models.CharField(max_length=255, blank=True, help_text="Lien interne vers le dossier concerné.")
    cree_le = models.DateTimeField(auto_now_add=True, db_index=True)
    lu = models.BooleanField(default=False)

    class Meta:
        ordering = ['-cree_le']

    def __str__(self):
        return f"{self.message} → {self.destinataire}"


class ModificationPatient(models.Model):
    """Traçabilité des modifications administratives (US3.2 / UC2).

    Chaque changement d'un champ administratif du patient est enregistré
    avec son auteur, la valeur précédente et la valeur nouvelle.
    """

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='modifications',
    )
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='modifications_patients',
        help_text="Infirmier auteur de la modification.",
    )
    champ = models.CharField(max_length=100)
    ancienne_valeur = models.TextField(blank=True)
    nouvelle_valeur = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-cree_le']

    def __str__(self):
        return f"{self.patient.ndp} — {self.champ} ({self.cree_le:%d/%m/%Y %H:%M})"


class VerrouDossier(models.Model):
    """Verrou temporaire d'un dossier en édition (UC2 / Ex1).

    Empêche deux utilisateurs de modifier simultanément les informations
    administratives d'un même patient. Le verrou expire automatiquement
    après `DUREE_VERROU` minutes.
    """

    DUREE_VERROU_MINUTES = 15

    patient = models.OneToOneField(
        Patient,
        on_delete=models.CASCADE,
        related_name='verrou',
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verrous_dossiers',
    )
    cree_le = models.DateTimeField(auto_now_add=True)
    expire_le = models.DateTimeField()

    def __str__(self):
        return f"Verrou {self.patient.ndp} — {self.utilisateur} (expire {self.expire_le:%d/%m/%Y %H:%M})"

    @property
    def est_actif(self):
        return timezone.now() < self.expire_le


# ---------------------------------------------------------------------------
# Epic 4 — Suivi thérapeutique (US4.1, US4.2, US4.3)
# ---------------------------------------------------------------------------


class CategorieSchemaTraitement(models.TextChoices):
    NOUVEAU_CAS = 'NOUVEAU_CAS', 'Nouveau cas'
    RETRAITEMENT = 'RETRAITEMENT', 'Retraitement (Catégorie II)'


class TypeCasTraitement(models.TextChoices):
    NOUVEAU = 'NOUVEAU', 'Nouveau cas'
    RECHUTE = 'RECHUTE', 'Rechute'


class StatutTraitement(models.TextChoices):
    EN_COURS = 'EN_COURS', 'En cours'
    CLOTURE = 'CLOTURE', 'Clôturé'


class IssueFinale(models.TextChoices):
    GUERI = 'GUERI', 'Guéri'
    TERMINE = 'TERMINE', 'Traitement terminé'
    ECHEC = 'ECHEC', 'Échec du traitement'
    DECEDE = 'DECEDE', 'Décédé'
    PERDU_DE_VUE = 'PERDU_DE_VUE', 'Perdu de vue'
    TRANSFERE = 'TRANSFERE', 'Transféré'


class ModeObservation(models.TextChoices):
    PRIS_SOUS_SUPERVISION = 'X', 'X — Pris sous supervision (DOTS)'
    AUTO_ADMINISTRE = '-', '- — Auto-administré'
    ABSENT = 'O', 'O — Absent'
    RELAIS_COMMUNAUTAIRE = 'J', '↑ — Relais communautaire (ASC)'


class TypeModificationTraitement(models.TextChoices):
    CATEGORIE_II = 'CATEGORIE_II', 'Passage en Catégorie II (retraitement)'
    SUSPENSION_MEDICAMENT = 'SUSPENSION', 'Suspension d’un médicament'
    CHANGEMENT_POSOLOGIE = 'POSOLOGIE', 'Changement de posologie'


class TypeRendezVous(models.TextChoices):
    CONTROLE_MENSUEL = 'CONTROLE', 'Contrôle mensuel'
    REMISE_MEDICAMENTS = 'MEDICAMENTS', 'Remise de médicaments'
    RESULTATS_C2 = 'C2', 'Lecture des résultats C2'
    RESULTATS_C5 = 'C5', 'Lecture des résultats C5'
    FIN_TRAITEMENT = 'FIN', 'Fin de traitement'
    SUIVI_CLINIQUE = 'CLINIQUE', 'Suivi clinique'
    AUTRE = 'AUTRE', 'Autre'


class StatutRendezVous(models.TextChoices):
    PLANIFIE = 'PLANIFIE', 'Planifié'
    EFFECTUE = 'EFFECTUE', 'Effectué'
    ANNULE = 'ANNULE', 'Annulé'


class SchemaTraitement(models.Model):
    """Schéma thérapeutique antituberculeux (ex. 2 RHZE / 4 RH)."""

    code = models.CharField(max_length=30, unique=True)
    libelle = models.CharField(max_length=120)
    categorie = models.CharField(
        max_length=20,
        choices=CategorieSchemaTraitement.choices,
        default=CategorieSchemaTraitement.NOUVEAU_CAS,
    )
    actif = models.BooleanField(default=True)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['ordre']

    def __str__(self):
        return self.libelle

    @property
    def phases_listees(self):
        return " / ".join(
            f"{phase.duree_mois} {phase.medicament}"
            for phase in self.phases.all()
        )

    @property
    def duree_totale_mois(self):
        return sum(phase.duree_mois for phase in self.phases.all())


class PhaseSchemaTraitement(models.Model):
    """Une phase du schéma : durée en mois et médicaments associés."""

    schema = models.ForeignKey(
        SchemaTraitement,
        on_delete=models.CASCADE,
        related_name='phases',
    )
    ordre = models.PositiveSmallIntegerField(default=1)
    duree_mois = models.PositiveSmallIntegerField()
    medicament = models.CharField(
        max_length=30,
        help_text="Code du médicament, ex. RHZE, RH, SRHZE, RHE.",
    )
    intensive = models.BooleanField(
        default=False,
        help_text="Phase intensive (2 premiers mois) ou phase de continuation.",
    )

    class Meta:
        ordering = ['schema', 'ordre']
        constraints = [
            models.UniqueConstraint(
                fields=['schema', 'ordre'],
                name='unique_phase_par_schema_ordre',
            ),
        ]

    def __str__(self):
        return f"{self.schema.code} · {self.duree_mois} {self.medicament}"


class Traitement(models.Model):
    """US4.1 / US4.3 — Fiche de traitement antituberculeux du patient.

    Le schéma et la posologie journalière (comprimés/jour) sont calculés
    automatiquement à partir du poids ; le schéma peut être modifié
    (Catégorie II, suspension, posologie) avec traçabilité dans
    `HistoriqueModificationTraitement`.
    """

    patient = models.OneToOneField(
        Patient,
        on_delete=models.CASCADE,
        related_name='traitement',
    )
    schema = models.ForeignKey(
        SchemaTraitement,
        on_delete=models.PROTECT,
        related_name='traitements',
    )
    type_cas = models.CharField(max_length=20, choices=TypeCasTraitement.choices)
    date_debut = models.DateField(db_index=True)
    poids_initial = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Poids au début du traitement, base du calcul de la posologie.",
    )
    posologie_jour = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Nombre de comprimés par jour, calculé selon le poids.",
    )
    unite_traitement = models.CharField(
        max_length=120,
        default='HGR Makala',
        help_text="Unité de traitement (TS, HGR…) pour le registre de cas.",
    )
    statut = models.CharField(
        max_length=20,
        choices=StatutTraitement.choices,
        default=StatutTraitement.EN_COURS,
    )
    issue_finale = models.CharField(
        max_length=20,
        choices=IssueFinale.choices,
        blank=True,
        help_text="Issue définitive du traitement (renseignée à la clôture).",
    )
    issue_decision_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date de l'issue finale (clôture du dossier).",
    )
    cloture_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='traitements_clotures',
        help_text="Médecin ayant clôturé le dossier.",
    )
    perdu_de_vue = models.DateField(
        null=True,
        blank=True,
        help_text="Date d'alerte « perdu de vue » (aucune prise depuis 2 mois).",
    )
    notes = models.TextField(
        blank=True,
        help_text="Notes générales sur le suivi thérapeutique.",
    )
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='traitements_crees',
        help_text="Médecin prescripteur du traitement.",
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_debut']

    def __str__(self):
        issue = f" · {self.get_issue_finale_display()}" if self.issue_finale else ""
        return f"{self.patient.ndp} — {self.schema.code} ({self.date_debut:%d/%m/%Y}){issue}"

    @property
    def date_fin_prevue(self):
        date = self.date_debut
        for _ in range(self.schema.duree_totale_mois):
            mois = date.month - 1
            annee = date.year
            annee += mois // 12
            mois = mois % 12 + 1
            jour = min(date.day, [31, 29 if annee % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mois - 1])
            date = date.replace(year=annee, month=mois, day=jour)
        return date

    @property
    def est_en_cours(self):
        return self.statut == StatutTraitement.EN_COURS

    @property
    def a_recuperer(self):
        return self.perdu_de_vue is not None and self.est_en_cours

    @property
    def poids_actuel(self):
        visite = self.visites.order_by('-date').first()
        if visite is not None and visite.poids is not None:
            return visite.poids
        return self.poids_initial


class ObservanceJournaliere(models.Model):
    """US4.1 — Observance d'une prise au jour J d'un mois de traitement.

    Codes : X = pris sous supervision (DOTS), - = auto-administré,
    O = absent, ↑ (J) = relais communautaire (ASC).
    """

    EVENEMENTS = (ModeObservation.PRIS_SOUS_SUPERVISION,
                  ModeObservation.AUTO_ADMINISTRE, ModeObservation.RELAIS_COMMUNAUTAIRE)

    traitement = models.ForeignKey(
        Traitement,
        on_delete=models.CASCADE,
        related_name='observances',
    )
    mois = models.PositiveSmallIntegerField(
        help_text="Mois de traitement (1 = premier mois)."
    )
    jour = models.PositiveSmallIntegerField()
    statut = models.CharField(max_length=1, choices=ModeObservation.choices)
    cree_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['mois', 'jour']
        constraints = [
            models.UniqueConstraint(
                fields=['traitement', 'mois', 'jour'],
                name='unique_observance_traitement_mois_jour',
            ),
        ]

    def __str__(self):
        return f"{self.traitement.patient.ndp} — M{self.mois} J{self.jour} : {self.statut}"


class VisiteSuivi(models.Model):
    """US4.1 — Visite de suivi clinique (poids, signes d'alerte)."""

    traitement = models.ForeignKey(
        Traitement,
        on_delete=models.CASCADE,
        related_name='visites',
    )
    date = models.DateField(db_index=True)
    poids = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Poids actuel du patient (kg).",
    )
    troubles_visuels = models.BooleanField(
        default=False, help_text="Troubles visuels (signe d'alerte)."
    )
    jaunisse = models.BooleanField(default=False, help_text="Jaunisse / ictère.")
    eruption_cutanee = models.BooleanField(default=False, help_text="Éruptions cutanées.")
    vertiges = models.BooleanField(default=False, help_text="Vertiges.")
    autres_effets = models.TextField(
        blank=True,
        help_text="Autres effets indésirables signalés par le patient.",
    )
    observations = models.TextField(
        blank=True,
        help_text="Observations cliniques de la visite.",
    )
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='visites_suivi',
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-cree_le']

    def __str__(self):
        return f"{self.traitement.patient.ndp} — visite du {self.date:%d/%m/%Y}"

    @property
    def signes_alerte(self):
        libelles = {
            'troubles_visuels': 'Troubles visuels',
            'jaunisse': 'Jaunisse',
            'eruption_cutanee': 'Éruptions cutanées',
            'vertiges': 'Vertiges',
        }
        return [libelle for champ, libelle in libelles.items() if getattr(self, champ)]


class HistoriqueModificationTraitement(models.Model):
    """US4.1 — Traçabilité des modifications du traitement (Catégorie II,
    suspension d'un médicament, changement de posologie).

    Toute modification exige un motif médical (champ obligatoire).
    """

    traitement = models.ForeignKey(
        Traitement,
        on_delete=models.CASCADE,
        related_name='modifications_traitement',
    )
    medecin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='modifications_traitements',
    )
    cree_le = models.DateTimeField(auto_now_add=True, db_index=True)
    type_modification = models.CharField(
        max_length=20,
        choices=TypeModificationTraitement.choices,
    )
    motif_medical = models.TextField(
        help_text="Motif médical de la modification (obligatoire)."
    )
    ancien_schema = models.ForeignKey(
        SchemaTraitement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='+',
    )
    nouveau_schema = models.ForeignKey(
        SchemaTraitement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='+',
    )
    ancien_posologie_jour = models.PositiveSmallIntegerField(null=True, blank=True)
    nouveau_posologie_jour = models.PositiveSmallIntegerField(null=True, blank=True)
    medicament_suspendu = models.CharField(
        max_length=30,
        blank=True,
        help_text="Médicament suspendu (ex. EH, S).",
    )
    description = models.TextField(
        blank=True,
        help_text="Précisions complémentaires sur la modification.",
    )

    class Meta:
        ordering = ['-cree_le']

    def __str__(self):
        return f"{self.traitement.patient.ndp} — {self.get_type_modification_display()} ({self.cree_le:%d/%m/%Y %H:%M})"


class RendezVous(models.Model):
    """US4.3 — Rendez-vous de suivi du malade (carte du malade).

    Agenda partagé : un rendez-vous planifié bloque la case (date + heure)
    pour toute autre planification dans le service.
    """

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='rendez_vous',
    )
    date = models.DateField(db_index=True)
    heure = models.TimeField()
    type = models.CharField(max_length=20, choices=TypeRendezVous.choices)
    statut = models.CharField(
        max_length=20,
        choices=StatutRendezVous.choices,
        default=StatutRendezVous.PLANIFIE,
    )
    motif = models.CharField(
        max_length=200,
        blank=True,
        help_text="Précision sur l'objet du rendez-vous.",
    )
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='rendez_vous_crees',
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'heure']

    def __str__(self):
        return f"{self.patient.ndp} — {self.date:%d/%m/%Y} {self.heure:%H:%M} ({self.get_statut_display()})"

    @property
    def est_planifie(self):
        return self.statut == StatutRendezVous.PLANIFIE