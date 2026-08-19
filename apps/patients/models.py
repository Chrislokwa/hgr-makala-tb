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