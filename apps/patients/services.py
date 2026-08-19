from django.db import IntegrityError, transaction

from .models import ExamenPrescription, Patient, StatutDossier, StatutExamen


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


def creer_prescription_examen(*, medecin, patient, donnees, types_examens):
    donnees = dict(donnees)
    for _ in range(5):
        try:
            with transaction.atomic():
                prescription = ExamenPrescription(
                    medecin=medecin,
                    patient=patient,
                    **donnees,
                )
                prescription.save()
                prescription.examens.set(types_examens)
                return prescription
        except IntegrityError:
            continue
    raise IntegrityError("Échec de la création de la demande (numéro de demande unique).")


def trouver_prescriptions_en_attente(patient, codes_types):
    """Demandes identiques (même type, statut « En attente ») déjà en cours.

    Le test VIH, systématiquement pré-coché pour tout suspect, est exclu de la
    comparaison : seul un doublon sur les examens diagnostiques spécifiques
    (bacilloscopie, GeneXpert, culture, DST) est signalé.
    """
    codes_significatifs = [code for code in codes_types if code != 'VIH']
    if not codes_significatifs:
        return ExamenPrescription.objects.none()
    return (
        ExamenPrescription.objects
        .filter(patient=patient, statut=StatutExamen.EN_ATTENTE)
        .filter(examens__code__in=codes_significatifs)
        .distinct()
        .order_by('-date_prescription')
    )