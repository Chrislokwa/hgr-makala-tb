from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.users.models import CustomUser, UserRole

from .models import (
    DecisionDiagnostic,
    ExamenPrescription,
    InterpretationResultat,
    ModificationPatient,
    Notification,
    Patient,
    ResultatLabo,
    StatutDossier,
    StatutExamen,
    StatutResultat,
    VerrouDossier,
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


# ---------------------------------------------------------------------------
# Epic 3 — Gestion administrative des dossiers patient
# ---------------------------------------------------------------------------


CHAMPS_ADMINISTRATIFS = (
    'nom',
    'post_nom',
    'prenom',
    'sexe',
    'date_naissance',
    'district',
    'secteur',
    'cellule',
    'village',
    'telephone',
)


def admission_est_finalisable(patient):
    """Garde-fou métier (Fonction 3).

    L'infirmier ne peut compléter et finaliser l'admission que si le
    diagnostic a été confirmé et les résultats de laboratoire saisis.
    """
    if patient.statut != StatutDossier.CONFIRME:
        return False
    return ResultatLabo.objects.filter(
        prescription__patient=patient,
        statut=StatutResultat.VALIDE,
    ).exists()


def finaliser_admission(*, infirmier, patient, donnees):
    """US3.1 / UC1 — Finalise l'admission administrative du patient.

    Complète les données administratives obligatoires, contrôle les
    doublons (Nom + Prénom + Date de naissance) puis marque l'admission
    comme finalisée avec l'horodatage et l'infirmier auteur.
    """
    from django.core.exceptions import ValidationError

    if patient.admission_finalisee:
        raise ValidationError("L'admission de ce patient est déjà finalisée.")

    champs = {cle: donnees.get(cle) for cle in CHAMPS_ADMINISTRATIFS}
    manquants = [
        libelle for cle, libelle in
        (('nom', 'Nom'), ('prenom', 'Prénom'), ('sexe', 'Sexe'), ('date_naissance', 'Date de naissance'))
        if not champs.get(cle)
    ]
    if manquants:
        raise ValidationError(
            "Champs obligatoires manquants : " + ", ".join(manquants) + "."
        )

    doublon = Patient.trouver_doublon(
        champs['nom'], champs['prenom'], champs['date_naissance'],
        exclure=patient,
    )
    if doublon:
        return doublon, True

    with transaction.atomic():
        for champ, valeur in champs.items():
            ancienne = getattr(patient, champ)
            if ancienne != valeur:
                enregistrer_modification(
                    patient=patient,
                    auteur=infirmier,
                    champ=champ,
                    ancienne_valeur=str(ancienne) if ancienne not in (None, '') else '',
                    nouvelle_valeur=str(valeur) if valeur not in (None, '') else '',
                )
                setattr(patient, champ, valeur)
        patient.date_admission = timezone.now()
        patient.admise_par = infirmier
        patient.save()
    return patient, False


def enregistrer_modification(*, patient, auteur, champ, ancienne_valeur, nouvelle_valeur):
    """US3.2 / UC2 — Enregistre une modification pour traçabilité."""
    ModificationPatient.objects.create(
        patient=patient,
        auteur=auteur,
        champ=champ,
        ancienne_valeur=ancienne_valeur or '',
        nouvelle_valeur=nouvelle_valeur or '',
    )


def mettre_a_jour_informations(*, infirmier, patient, donnees):
    """US3.2 / UC2 — Met à jour les informations administratives.

    Conserve l'historique de chaque champ modifié (date, heure, auteur).
    """
    with transaction.atomic():
        for champ in CHAMPS_ADMINISTRATIFS:
            if champ not in donnees:
                continue
            nouvelle = donnees.get(champ)
            ancienne = getattr(patient, champ)
            if ancienne != nouvelle:
                enregistrer_modification(
                    patient=patient,
                    auteur=infirmier,
                    champ=champ,
                    ancienne_valeur=str(ancienne) if ancienne not in (None, '') else '',
                    nouvelle_valeur=str(nouvelle) if nouvelle not in (None, '') else '',
                )
                setattr(patient, champ, nouvelle)
        patient.save()
    return patient


def acquerir_verrou(patient, utilisateur):
    """Tente d'obtenir le verrou d'édition du dossier (UC2 / Ex1).

    Retourne le verrou s'il est actif et détenu par un autre utilisateur,
    None si le verrou a été obtenu (ou renouvelé).
    """
    verrou = VerrouDossier.objects.filter(patient=patient).select_related('utilisateur').first()
    if verrou is not None and verrou.est_actif and verrou.utilisateur != utilisateur:
        return verrou
    VerrouDossier.objects.update_or_create(
        patient=patient,
        defaults={
            'utilisateur': utilisateur,
            'expire_le': timezone.now() + timezone.timedelta(minutes=VerrouDossier.DUREE_VERROU_MINUTES),
        },
    )
    return None


def liberer_verrou(patient, utilisateur):
    """Libère le verrou détenu par l'utilisateur sur le dossier."""
    VerrouDossier.objects.filter(patient=patient, utilisateur=utilisateur).delete()