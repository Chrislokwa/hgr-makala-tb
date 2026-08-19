from django.db import IntegrityError, transaction

from .models import Patient, StatutDossier


def creer_dossier_provisoire(*, medecin, donnees):
    donnees = dict(donnees)
    donnees['statut'] = StatutDossier.PROVISOIRE
    for _ in range(5):
        try:
            with transaction.atomic():
                patient = Patient(cree_par=medecin, **donnees)
                patient.save()
                return patient
        except IntegrityError:
            continue
    raise IntegrityError("Échec de la création du dossier (numéro de dossier unique).")