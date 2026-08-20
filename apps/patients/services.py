from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.users.models import CustomUser, UserRole

from .models import (
    DecisionDiagnostic,
    ExamenPrescription,
    InterpretationResultat,
    Notification,
    Patient,
    ResultatLabo,
    StatutDossier,
    StatutExamen,
    StatutResultat,
)


def _notifier_laborantins(prescription):
    """Notifie tous les laborantins actifs d'une nouvelle demande à traiter."""
    laborantins = CustomUser.objects.filter(
        is_active=True, role=UserRole.LABORANTIN
    )
    for laborantin in laborantins:
        Notification.objects.create(
            destinataire=laborantin,
            message=(
                f"Nouvelle demande à traiter : {prescription.numero_demande} — "
                f"{prescription.patient.full_name} ({prescription.types_libelles})."
            ),
            url="/examens/",
        )


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
                _notifier_laborantins(prescription)
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


def _sauvegarder_resultat(*, laborantin, prescription, donnees, statut, date_lecture):
    resultat = (
        ResultatLabo.objects.filter(prescription=prescription)
        .order_by('-cree_le')
        .first()
    )
    if resultat is None:
        resultat = ResultatLabo(prescription=prescription, laborantin=laborantin)
    for champ, valeur in donnees.items():
        setattr(resultat, champ, valeur)
    resultat.laborantin = laborantin
    resultat.statut = statut
    resultat.date_lecture = date_lecture
    resultat.save()
    return resultat


def enregistrer_resultats(*, laborantin, prescription, donnees, valider):
    """Sauvegarde les résultats d'une demande de laboratoire.

    - Entrée simple : modifie la dernière entrée existante (brouillon le plus
      récent, sinon le résultat validé affiché au médecin).
    - Validation : si un résultat validé existe déjà, une nouvelle entrée est
      créée (version précédente conservée pour traçabilité) ; sinon l'entrée
      courante est promue au statut VALIDE. Le statut de la demande passe à
      « Résultats disponibles » et une notification est envoyée au médecin.
    """
    with transaction.atomic():
        if valider:
            deja_valide = ResultatLabo.objects.filter(
                prescription=prescription, statut=StatutResultat.VALIDE
            ).exists()
            if deja_valide:
                resultat = ResultatLabo(
                    prescription=prescription,
                    laborantin=laborantin,
                    statut=StatutResultat.VALIDE,
                    date_lecture=timezone.now(),
                    **donnees,
                )
                resultat.save()
            else:
                resultat = _sauvegarder_resultat(
                    laborantin=laborantin,
                    prescription=prescription,
                    donnees=donnees,
                    statut=StatutResultat.VALIDE,
                    date_lecture=timezone.now(),
                )
            prescription.statut = StatutExamen.RESULTATS_DISPONIBLES
            prescription.save(update_fields=['statut'])
            Notification.objects.create(
                destinataire=prescription.medecin,
                message=(
                    f"Résultats disponibles : {prescription.numero_demande} — "
                    f"{prescription.patient.full_name} ({prescription.types_libelles})."
                ),
                url=f"/patients/{prescription.patient.pk}/",
            )
            return resultat

        return _sauvegarder_resultat(
            laborantin=laborantin,
            prescription=prescription,
            donnees=donnees,
            statut=StatutResultat.BROUILLON,
            date_lecture=None,
        )


def enregistrer_interpretation(*, medecin, prescription, donnees):
    """Enregistre l'analyse médicale du médecin et applique la décision.

    L'enregistrement déclenche le point d'extension « Décision de
    diagnostic » :
    - Tuberculose confirmée (UC7) : le dossier passe au statut « Confirmé ».
    - Tuberculose infirmée (UC8) : le dossier passe au statut « Non confirmé ».
    Une seule interprétation est conservée par prescription.
    """
    donnees = dict(donnees)
    decision = donnees.get('decision')
    if decision not in (DecisionDiagnostic.CONFIRMEE, DecisionDiagnostic.INFIRMEE):
        raise ValueError("Décision de diagnostic invalide.")

    with transaction.atomic():
        interpretation, _ = InterpretationResultat.objects.update_or_create(
            prescription=prescription,
            defaults={
                'medecin': medecin,
                'observations': donnees.get('observations', ''),
                'interpretation': donnees.get('interpretation', ''),
                'decision': decision,
            },
        )
        patient = prescription.patient
        patient.statut = (
            StatutDossier.CONFIRME
            if decision == DecisionDiagnostic.CONFIRMEE
            else StatutDossier.NON_CONFIRME
        )
        patient.save(update_fields=['statut'])
        infirmiers = CustomUser.objects.filter(
            is_active=True, role=UserRole.INFIRMIER
        )
        for infirmier in infirmiers:
            Notification.objects.create(
                destinataire=infirmier,
                message=(
                    f"Dossier {patient.ndp} ({patient.full_name}) "
                    f"{'confirmé — admission à finaliser' if decision == DecisionDiagnostic.CONFIRMEE else 'non confirmé — admission annulée'}."
                ),
                url=f"/patients/{patient.pk}/",
            )
        return interpretation