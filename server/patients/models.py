from django.db import models
from django.conf import settings

class Patient(models.Model):
    GENDER_CHOICES = (
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    )

    code_patient = models.CharField(max_length=50, unique=True)
    nom = models.CharField(max_length=100)
    postnom = models.CharField(max_length=100, blank=True, null=True)
    prenom = models.CharField(max_length=100)
    sexe = models.CharField(max_length=1, choices=GENDER_CHOICES)
    age = models.IntegerField()
    adresse = models.TextField()
    telephone = models.CharField(max_length=20, blank=True, null=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='patients_crees'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code_patient} - {self.nom} {self.prenom}"


class DossierTraitement(models.Model):
    CATEGORIE_CHOICES = (
        ('NOUVEAU', 'Nouveau cas'),
        ('RECHUTE', 'Rechute'),
        ('ECHEC', 'Échec de traitement'),
        ('REPRISE', 'Reprise après abandon'),
    )

    STATUT_CHOICES = (
        ('EN_COURS', 'En cours'),
        ('GUERI', 'Guéri'),
        ('TERMINE', 'Traitement terminé'),
        ('ECHEC', 'Échec'),
        ('DECEDE', 'Décédé'),
        ('PERDU', 'Perdu de vue'),
    )

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='dossiers')
    numero_tb = models.CharField(max_length=50, unique=True)
    categorie = models.CharField(max_length=20, choices=CATEGORIE_CHOICES, default='NOUVEAU')
    regime_traitement = models.CharField(max_length=100) # Ex: 2RHZE/4RH
    poids_initial = models.FloatField()
    date_debut_traitement = models.DateField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_COURS')
    medecin_traitant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='dossiers_suivis'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"TB: {self.numero_tb} - {self.patient.nom}"


class RendezVous(models.Model):
    STATUT_CHOICES = (
        ('PROGRAMME', 'Programmé'),
        ('HONORE', 'Honoré'),
        ('MANQUE', 'Manqué'),
        ('ANNULE', 'Annulé'),
    )

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='rendezvous')
    dossier = models.ForeignKey(DossierTraitement, on_delete=models.CASCADE, related_name='rendezvous', null=True, blank=True)
    date_rendez_vous = models.DateTimeField()
    motif = models.CharField(max_length=255, blank=True, null=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='PROGRAMME')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"RDV {self.patient.nom} le {self.date_rendez_vous}"


class SuiviTherapeutique(models.Model):
    dossier = models.ForeignKey(DossierTraitement, on_delete=models.CASCADE, related_name='suivis')
    date_visite = models.DateField(auto_now_add=True)
    poids_actuel = models.FloatField()
    observance_traitement = models.BooleanField(default=True, help_text="Le patient prend-il régulièrement ses médicaments ?")
    effets_secondaires = models.TextField(blank=True, null=True)
    evolution_clinique = models.TextField(help_text="Rapport d'évolution rédigé par l'infirmier")
    enregistre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='suivis_enregistres'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Suivi du {self.date_visite} - TB: {self.dossier.numero_tb}"


