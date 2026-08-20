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
    CONFIRME = 'CONFIRME', 'Confirmé'
    NON_CONFIRME = 'NON_CONFIRME', 'Non confirmé'


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
    comorb_vih = models.BooleanField(default=False)
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
    def trouver_doublon(cls, nom, prenom, date_naissance):
        return (
            cls.objects
            .filter(
                nom__iexact=nom,
                prenom__iexact=prenom,
                date_naissance=date_naissance,
            )
            .exclude(statut=StatutDossier.NON_CONFIRME)
            .order_by('-cree_le')
            .first()
        )

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
            'comorb_vih': 'VIH/SIDA (connu)',
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


class StatutVihConnu(models.TextChoices):
    POSITIF = 'POSITIF', 'Positif'
    NEGATIF = 'NEGATIF', 'Négatif'
    INCONNU = 'INCONNU', 'Inconnu'


class StatutExamen(models.TextChoices):
    EN_ATTENTE = 'EN_ATTENTE', 'En attente au laboratoire'
    RESULTATS_DISPONIBLES = 'RESULTATS_DISPONIBLES', 'Résultats disponibles'


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


class ResultatVih(models.TextChoices):
    POSITIF = 'POSITIF', 'Positif'
    NEGATIF = 'NEGATIF', 'Négatif'
    PVV = 'PVV', 'PVV déjà connu'
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
    statut_vih = models.CharField(
        max_length=20,
        choices=StatutVihConnu.choices,
        blank=True,
        help_text="Statut VIH connu du patient (optionnel).",
    )
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
        default=StatutResultat.BROUILLON,
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
    resultat_vih = models.CharField(
        max_length=20,
        choices=ResultatVih.choices,
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
        if self.resultat_vih == ResultatVih.POSITIF:
            positifs.append("Test VIH : Positif")
        return positifs


class InterpretationResultat(models.Model):
    """Analyse médicale par le médecin traitant des résultats validés.

    L'enregistrement de l'interprétation déclenche le point d'extension
    « Décision de diagnostic » : la tuberculose est confirmée (UC7 —
    validation de l'admission) ou infirmée (UC8 — annulation de l'admission).
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
    def statut_dossier_cible(self):
        if self.decision == DecisionDiagnostic.CONFIRMEE:
            return StatutDossier.CONFIRME
        return StatutDossier.NON_CONFIRME

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