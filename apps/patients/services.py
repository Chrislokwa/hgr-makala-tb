from calendar import monthrange
from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.users.models import CustomUser, UserRole

from .models import (
    CategorieSchemaTraitement,
    DecisionDiagnostic,
    EpisodeTB,
    ExamenPrescription,
    HistoriqueModificationTraitement,
    InterpretationResultat,
    IssueFinale,
    ModificationPatient,
    ModeObservation,
    MoisControle,
    MotifExamen,
    Notification,
    ObservanceJournaliere,
    Patient,
    RendezVous,
    ResultatLabo,
    SchemaTraitement,
    SiteMaladie,
    StatutDossier,
    StatutEpisodeTB,
    StatutExamen,
    StatutRendezVous,
    StatutResultat,
    StatutTraitement,
    Traitement,
    TypeCasTraitement,
    TypeModificationTraitement,
    TypePatient,
    VerrouDossier,
    VisiteSuivi,
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


def _schema_pour_type_cas(type_cas):
    """Sélectionne le schéma thérapeutique actif selon le type de cas."""
    from django.core.exceptions import ValidationError

    if type_cas not in TypeCasTraitement.values:
        raise ValidationError("Type de cas de tuberculose invalide.")
    categorie = (
        CategorieSchemaTraitement.RETRAITEMENT
        if type_cas == TypeCasTraitement.RECHUTE
        else CategorieSchemaTraitement.NOUVEAU_CAS
    )
    schema = (
        SchemaTraitement.objects
        .filter(categorie=categorie, actif=True)
        .order_by('ordre')
        .first()
    )
    if schema is None:
        raise ValidationError("Aucun schéma thérapeutique applicable n'est disponible.")
    return schema


def creer_dossier_provisoire(*, medecin, donnees):
    """Crée le dossier provisoire du patient et l'épisode de maladie TB.

    Le médecin renseigne les données du patient (identité, adresse) et
    les paramètres de l'épisode (type de patient, site de la maladie,
    diagnostic initial). Le NDP, la date d'ouverture et le statut sont
    générés automatiquement.
    """
    donnees = dict(donnees)
    # Extraire les données de l'épisode
    episode_donnees = {
        'type_patient': donnees.pop('type_patient', None) or TypePatient.NOUVEAU,
        'site_maladie': donnees.pop('site_maladie', None) or SiteMaladie.TPM_PLUS,
        'diagnostic': donnees.pop('diagnostic', ''),
    }

    for _ in range(5):
        try:
            with transaction.atomic():
                patient = Patient(cree_par=medecin, **donnees)
                patient.save()
                EpisodeTB.objects.create(
                    patient=patient,
                    statut=StatutEpisodeTB.PROVISOIRE,
                    type_patient=episode_donnees['type_patient'],
                    site_maladie=episode_donnees['site_maladie'],
                    diagnostic=episode_donnees['diagnostic'],
                    cree_par=medecin,
                )
                break
        except IntegrityError:
            continue
    else:
        raise IntegrityError("Échec de la création du dossier (numéro de dossier unique).")

    for infirmier in CustomUser.objects.filter(is_active=True, role=UserRole.INFIRMIER):
        Notification.objects.create(
            destinataire=infirmier,
            message=(
                f"Nouveau dossier provisoire : {patient.ndp} ({patient.full_name}) — "
                f"épisode TB créé, admission à valider."
            ),
            url=f"/patients/{patient.pk}/",
        )
    return patient


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

    Seul un doublon sur les examens diagnostiques spécifiques (bacilloscopie,
    GeneXpert, culture, DST) est signalé.
    """
    if not codes_types:
        return ExamenPrescription.objects.none()
    return (
        ExamenPrescription.objects
        .filter(patient=patient, statut=StatutExamen.EN_ATTENTE)
        .filter(examens__code__in=codes_types)
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


def enregistrer_resultats(*, laborantin, prescription, donnees):
    """Sauvegarde et valide les résultats d'une demande de laboratoire.

    La gestion des brouillons est supprimée : chaque saisie est directement
    validée. Si un résultat validé existe déjà, une nouvelle entrée est
    créée (version précédente conservée pour traçabilité) ; sinon l'entrée
    courante est promue au statut VALIDE. Le statut de la demande passe à
    « Résultats disponibles » et une notification est envoyée au médecin.
    """
    with transaction.atomic():
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


def enregistrer_interpretation(*, medecin, prescription, donnees):
    """Enregistre l'analyse médicale du médecin et la décision de diagnostic.

    La décision met à jour le statut du dossier :
    - CONFIRMEE -> CONFIRME (en attente d'admission)
    - INFIRMEE  -> NEGATIF / NON_CONFIRME (diagnostic infirmé, statut négatif)
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
        nouveau_statut = (
            StatutDossier.CONFIRME if decision == DecisionDiagnostic.CONFIRMEE
            else StatutDossier.NON_CONFIRME
        )
        if patient.statut != nouveau_statut:
            patient.statut = nouveau_statut
            patient.save(update_fields=['statut'])
        # Notifier les infirmiers
        for infirmier in CustomUser.objects.filter(is_active=True, role=UserRole.INFIRMIER):
            msg = (
                f"Diagnostic {'confirmé' if decision == DecisionDiagnostic.CONFIRMEE else 'infirmé (négatif)'} : "
                f"{patient.ndp} ({patient.full_name}) — {prescription.numero_demande}"
            )
            Notification.objects.create(
                destinataire=infirmier,
                message=msg,
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


def finaliser_admission(*, infirmier, patient, donnees):
    """US3.1 / UC1 — Finalise l'admission administrative du patient.

    L'infirmier complète les données administratives obligatoires, contrôle
    les doublons (Nom + Prénom + Date de naissance) puis valide
    l'admission : le dossier passe au statut « En traitement » — le schéma
    thérapeutique ayant déjà été prescrit à la création du dossier.
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
        patient.statut = StatutDossier.EN_TRAITEMENT
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


# ---------------------------------------------------------------------------
# Epic 4 — Suivi thérapeutique (US4.1, US4.2, US4.3)
# ---------------------------------------------------------------------------

BANDES_POSOLOGIE = [
    (30, 38, 2),
    (38, 55, 3),
    (55, 71, 4),
    (71, None, 5),
]
DELAI_PERDU_DE_VUE_JOURS = 60

CONTROLES_SUIVI = (
    MoisControle.C2,
    MoisControle.C3,
    MoisControle.C4,
    MoisControle.C5,
    MoisControle.C6,
    MoisControle.FIN,
)


def calculer_posologie(poids):
    """Nombre de comprimés/jour calculé à partir du poids (bandes adultes).

    Retourne None si le poids manque ou sort des bandes adultes
    (ex. moins de 30 kg, nécessitant une adaptation pédiatrique).
    """
    if poids in (None, ''):
        return None
    poids = float(poids)
    for borne_min, borne_max, comprimes in BANDES_POSOLOGIE:
        if poids >= borne_min and (borne_max is None or poids < borne_max):
            return comprimes
    return None


def bande_posologie_libelle(poids):
    if poids in (None, ''):
        return ''
    poids = float(poids)
    for borne_min, borne_max, comprimes in BANDES_POSOLOGIE:
        if poids >= borne_min and (borne_max is None or poids < borne_max):
            if borne_max is None:
                return f"{borne_min} kg et plus"
            return f"{borne_min}–{int(borne_max) - 1} kg"
    return 'Hors bandes (adaptation requise)'


def _date_mois_calendrier(traitement, mois):
    """Année et mois calendaires correspondant au mois de traitement `mois`."""
    decalage = traitement.date_debut.month - 1 + (mois - 1)
    annee = traitement.date_debut.year + decalage // 12
    mois_cal = decalage % 12 + 1
    return annee, mois_cal


def date_prise(traitement, mois, jour):
    """Date calendaire absolue d'une prise (mois de traitement, jour 1-31)."""
    annee, mois_cal = _date_mois_calendrier(traitement, mois)
    jour = min(jour, monthrange(annee, mois_cal)[1])
    return date(annee, mois_cal, jour)


def derniere_prise(traitement):
    """Retourne la date de la dernière prise observée (X / ↑ / -), ou None."""
    observation = (
        traitement.observances
        .filter(statut__in=ObservanceJournaliere.EVENEMENTS)
        .order_by('-mois', '-jour')
        .select_related()
        .first()
    )
    if observation is None:
        return None
    return date_prise(traitement, observation.mois, observation.jour)


def mois_traitement_libelle(traitement, mois):
    """Libellé du mois de traitement : « Mois 2 — 04/2026 »."""
    annee, mois_cal = _date_mois_calendrier(traitement, mois)
    return f"Mois {mois} — {mois_cal:02d}/{annee}"


def enregistrer_observance(*, utilisateur, traitement, mois, statuts_par_jour):
    """US4.1 — Enregistre la grille d'observance d'un mois (codes X, -, O, ↑).

    `statuts_par_jour` : dictionnaire {jour: code}. Une valeur vide efface la
    prise du jour. Toute reprise de prise efface l'alerte « perdu de vue ».
    """
    from django.core.exceptions import ValidationError

    if traitement.statut != StatutTraitement.EN_COURS:
        raise ValidationError("Ce traitement est clôturé : l'observance ne peut plus être modifiée.")
    if not 1 <= mois <= traitement.schema.duree_totale_mois:
        raise ValidationError(
            f"Mois de traitement invalide (1 à {traitement.schema.duree_totale_mois})."
        )

    codes_valides = set(ModeObservation.values)
    with transaction.atomic():
        for jour in range(1, 32):
            code = (statuts_par_jour.get(str(jour)) or '').strip()
            if code in codes_valides:
                ObservanceJournaliere.objects.update_or_create(
                    traitement=traitement,
                    mois=mois,
                    jour=jour,
                    defaults={'statut': code},
                )
            else:
                ObservanceJournaliere.objects.filter(
                    traitement=traitement, mois=mois, jour=jour
                ).delete()
        if traitement.perdu_de_vue is not None:
            traitement.perdu_de_vue = None
            traitement.save(update_fields=['perdu_de_vue'])
    return mois


def enregistrer_visite(*, auteur, traitement, donnees):
    """US4.1 — Zone 3 : visite de suivi clinique (poids actuel, signes d'alerte)."""
    from django.core.exceptions import ValidationError

    if traitement.statut != StatutTraitement.EN_COURS:
        raise ValidationError("Ce traitement est clôturé : aucune visite ne peut être ajoutée.")

    with transaction.atomic():
        visite = VisiteSuivi.objects.create(
            traitement=traitement,
            cree_par=auteur,
            **donnees,
        )
        if visite.poids is not None:
            patient = traitement.patient
            patient.poids = visite.poids
            patient.save(update_fields=['poids'])
        # Notifier le médecin prescripteur de chaque visite de contrôle (point 13)
        medecin = traitement.cree_par
        if medecin and medecin.is_active:
            Notification.objects.create(
                destinataire=medecin,
                message=(
                    f"Visite de contrôle enregistrée : {traitement.patient.ndp} "
                    f"({traitement.patient.full_name}) le {visite.date:%d/%m/%Y} "
                    f"par {auteur.titled_name}."
                ),
                url=f"/patients/{traitement.patient.pk}/traitement/",
            )
    return visite


def modifier_traitement(*, medecin, traitement, donnees):
    """US4.1 — Modifie le traitement (médecin uniquement), avec motif médical.

    Types de modification :
    - CATEGORIE_II : passage au schéma de retraitement (destiné à la rechute) ;
    - SUSPENSION : suspension temporaire d'un médicament ;
    - POSOLOGIE : changement de posologie (nombre de comprimés/jour).

    Chaque modification est historisée dans `HistoriqueModificationTraitement`.
    """
    from django.core.exceptions import ValidationError

    if traitement.statut != StatutTraitement.EN_COURS:
        raise ValidationError("Ce traitement est clôturé : aucune modification possible.")

    type_modif = donnees.get('type_modification')
    if type_modif not in TypeModificationTraitement.values:
        raise ValidationError("Type de modification invalide.")

    motif = (donnees.get('motif_medical') or '').strip()
    if not motif:
        raise ValidationError("Le motif médical de la modification est obligatoire.")

    ancien_schema = traitement.schema
    ancien_posologie = traitement.posologie_jour
    nouveau_schema = None
    nouveau_posologie = None
    medicament_suspendu = ''

    with transaction.atomic():
        if type_modif == TypeModificationTraitement.CATEGORIE_II:
            nouveau_schema = (
                SchemaTraitement.objects
                .filter(categorie=CategorieSchemaTraitement.RETRAITEMENT, actif=True)
                .order_by('ordre')
                .first()
            )
            if nouveau_schema is None:
                raise ValidationError("Aucun schéma de retraitement (Catégorie II) disponible.")
            traitement.schema = nouveau_schema
            traitement.posologie_jour = calculer_posologie(traitement.poids_actuel)
            traitement.save(update_fields=['schema', 'posologie_jour'])
            nouveau_posologie = traitement.posologie_jour

        elif type_modif == TypeModificationTraitement.SUSPENSION_MEDICAMENT:
            medicament_suspendu = (donnees.get('medicament_suspendu') or '').strip()
            if not medicament_suspendu:
                raise ValidationError("Précisez le médicament à suspendre (ex. EH, S).")

        elif type_modif == TypeModificationTraitement.CHANGEMENT_POSOLOGIE:
            nouveau_posologie = donnees.get('nouveau_posologie_jour')
            if not nouveau_posologie or nouveau_posologie < 1:
                raise ValidationError("Indiquez la nouvelle posologie (comprimés/jour).")
            traitement.posologie_jour = nouveau_posologie
            traitement.save(update_fields=['posologie_jour'])

        HistoriqueModificationTraitement.objects.create(
            traitement=traitement,
            medecin=medecin,
            type_modification=type_modif,
            motif_medical=motif,
            ancien_schema=ancien_schema if nouveau_schema is not None else None,
            nouveau_schema=nouveau_schema,
            ancien_posologie_jour=ancien_posologie,
            nouveau_posologie_jour=nouveau_posologie,
            medicament_suspendu=medicament_suspendu,
            description=(donnees.get('description') or '').strip(),
        )
    return traitement


def programmer_rendez_vous(*, auteur, patient, donnees):
    """US4.3 — Planifie un rendez-vous sur l'agenda partagé du service.

    Une même case (date + heure) ne peut être réservée qu'une seule fois :
    si un autre rendez-vous planifié occupe déjà la case, il est retourné
    comme conflit.
    """
    date_rdv = donnees['date']
    heure_rdv = donnees['heure']
    conflit = (
        RendezVous.objects
        .filter(date=date_rdv, heure=heure_rdv, statut=StatutRendezVous.PLANIFIE)
        .select_related('patient')
        .first()
    )
    if conflit is not None:
        return conflit, True

    with transaction.atomic():
        rdv = RendezVous.objects.create(
            patient=patient,
            date=date_rdv,
            heure=heure_rdv,
            type=donnees['type'],
            motif=donnees.get('motif', ''),
            cree_par=auteur,
        )
    return rdv, False


def statut_rendez_vous(*, utilisateur, rendez_vous, nouveau_statut):
    """US4.3 — Marque un rendez-vous comme effectué ou annulé."""
    from django.core.exceptions import ValidationError

    if nouveau_statut not in StatutRendezVous.values:
        raise ValidationError("Statut de rendez-vous invalide.")
    rendez_vous.statut = nouveau_statut
    rendez_vous.save(update_fields=['statut'])
    return rendez_vous


def detecter_perdus_de_vue(aujourdhui=None):
    """US4.3 — Signale les patients sans prise depuis 2 mois (« A récupérer »).

    Compare la dernière prise observée (ou le début de traitement si aucune
    prise) au seuil de 60 jours. Chaque patient signalé est notifié aux
    infirmiers et au médecin prescripteur.
    """
    aujourdhui = aujourdhui or timezone.localdate()
    seuil = aujourdhui - timedelta(days=DELAI_PERDU_DE_VUE_JOURS)
    traites = [
        traitement for traitement in
        Traitement.objects.filter(
            statut=StatutTraitement.EN_COURS, perdu_de_vue__isnull=True
        ).select_related('patient', 'cree_par')
        if (derniere_prise(traitement) or traitement.date_debut) < seuil
    ]
    for traitement in traites:
        traitement.perdu_de_vue = derniere_prise(traitement) or traitement.date_debut
        traitement.save(update_fields=['perdu_de_vue'])
        Notification.objects.create(
            destinataire=traitement.cree_par,
            message=(
                f"Perdu de vue : {traitement.patient.ndp} "
                f"({traitement.patient.full_name}) sans prise depuis 2 mois — "
                f"carte à récupérer."
            ),
            url=f"/patients/{traitement.patient.pk}/carte/",
        )
        for infirmier in CustomUser.objects.filter(is_active=True, role=UserRole.INFIRMIER):
            Notification.objects.create(
                destinataire=infirmier,
                message=(
                    f"Perdu de vue : {traitement.patient.ndp} "
                    f"({traitement.patient.full_name}) — carte à récupérer."
                ),
                url=f"/patients/{traitement.patient.pk}/carte/",
            )
    return traites


def cloturer_traitement(*, medecin, traitement, issue_finale, date_issue=None):
    """Clôture du dossier — issue finale évaluée par le médecin.

    La fiche devient en lecture seule ; ni observance, ni visite ni
    rendez-vous ne peuvent plus être modifiés. Le statut du patient est
    synchronisé : « Guéri » si l'issue est la guérison, sinon « Clôturé ».
    """
    from django.core.exceptions import ValidationError

    if traitement.statut != StatutTraitement.EN_COURS:
        raise ValidationError("Ce traitement est déjà clôturé.")
    if issue_finale not in IssueFinale.values:
        raise ValidationError("Issue finale invalide.")

    with transaction.atomic():
        traitement.statut = StatutTraitement.CLOTURE
        traitement.issue_finale = issue_finale
        traitement.issue_decision_date = date_issue or timezone.localdate()
        traitement.cloture_par = medecin
        traitement.save()
        patient = traitement.patient
        patient.statut = (
            StatutDossier.GUERI
            if issue_finale == IssueFinale.GUERI
            else StatutDossier.CLOTURE
        )
        patient.save(update_fields=['statut'])

    for infirmier in CustomUser.objects.filter(is_active=True, role=UserRole.INFIRMIER):
        Notification.objects.create(
            destinataire=infirmier,
            message=(
                f"Dossier {traitement.patient.ndp} ({traitement.patient.full_name}) "
                f"clôturé — {traitement.get_issue_finale_display()}."
            ),
            url=f"/patients/{traitement.patient.pk}/traitement/",
        )
    return traitement


def cohorte_guerison(annee, trimestre):
    """Pourcentage de guérison de la cohorte du trimestre (date de début)."""
    mois_debut = (trimestre - 1) * 3 + 1
    debut = date(annee, mois_debut, 1)
    mois_fin = mois_debut + 3
    annee_fin = annee + (mois_fin - 1) // 12
    mois_fin = (mois_fin - 1) % 12 + 1
    fin = date(annee_fin, mois_fin, 1)
    cohorte = Traitement.objects.filter(date_debut__gte=debut, date_debut__lt=fin)
    total = cohorte.count()
    gueris = cohorte.filter(issue_finale=IssueFinale.GUERI).count()
    return {
        'total': total,
        'gueris': gueris,
        'taux': round((gueris / total * 100), 1) if total else 0.0,
    }


def trouver_controle_en_attente(patient, mois_controle):
    """Bon de contrôle — Demande de contrôle en attente au laboratoire."""
    return (
        ExamenPrescription.objects
        .filter(
            patient=patient,
            motif=MotifExamen.SUIVI_CONTROLE,
            mois_controle=mois_controle,
            statut=StatutExamen.EN_ATTENTE,
        )
        .order_by('-date_prescription')
        .first()
    )


def resultat_controle(patient, code_mois):
    """Retourne (prescription, résultat validé) du contrôle C2/C5/… du patient."""
    prescription = (
        ExamenPrescription.objects
        .filter(
            patient=patient,
            motif=MotifExamen.SUIVI_CONTROLE,
            mois_controle=code_mois,
        )
        .order_by('-date_prescription')
        .first()
    )
    if prescription is None:
        return None, None
    return prescription, prescription.resultat_valide