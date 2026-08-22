from datetime import date
from calendar import monthrange
from django.db.models import Q, Count
from django.utils import timezone
from apps.patients.models import (
    Patient,
    ExamenPrescription,
    ResultatLabo,
    ResultatBacilloscopie,
    ResultatGeneXpert,
    MotifExamen,
    MoisControle,
    Traitement,
    TypeCasTraitement,
    IssueFinale,
    ObservanceJournaliere,
    ModeObservation,
    TypeExamen,
)


def periode_range(annee=None, trimestre=None, mois=None):
    """Retourne (debut, fin) datetime.date pour la période filtrée.

    - mois prime sur trimestre
    - trimestre = 1..4
    - annee défaut = année courante
    """
    today = timezone.localdate()
    annee = int(annee) if annee else today.year
    if mois:
        mois = int(mois)
        debut = date(annee, mois, 1)
        _, last = monthrange(annee, mois)
        fin = date(annee, mois, last)
        return debut, fin
    if trimestre:
        trimestre = int(trimestre)
        mois_debut = (trimestre - 1) * 3 + 1
        debut = date(annee, mois_debut, 1)
        mois_fin = mois_debut + 2
        _, last = monthrange(annee, mois_fin)
        fin = date(annee, mois_fin, last)
        return debut, fin
    # année entière
    return date(annee, 1, 1), date(annee, 12, 31)


def filtre_unite_queryset(queryset, unite, relation_prefix=""):
    """Applique filtre unité si fourni.

    relation_prefix: ex. 'patient__traitement__' pour ExamenPrescription
    """
    if unite:
        field = f"{relation_prefix}unite_traitement" if relation_prefix else "unite_traitement"
        return queryset.filter(**{field: unite})
    return queryset


def indicateurs_epidemiologiques(debut, fin, unite=None):
    # Suspects : patients testés au labo (distinct patients avec prescription dans période)
    base_prescriptions = ExamenPrescription.objects.filter(date_prescription__date__gte=debut, date_prescription__date__lte=fin)
    if unite:
        base_prescriptions = base_prescriptions.filter(patient__traitement__unite_traitement=unite)
    suspects_qs = base_prescriptions.values('patient').distinct()
    nb_suspects = suspects_qs.count()

    # TPM+ : patients avec résultat positif (BAAR positif ou GeneXpert MTB+)
    BAAR_POS = list(ResultatLabo.BAAR_POSITIFS)
    GENE_POS = [ResultatGeneXpert.MTB_PLUS_RIF_PLUS, ResultatGeneXpert.MTB_PLUS_RIF_MOINS, ResultatGeneXpert.MTB_MOINS_RIF_PLUS]
    resultats_positifs = ResultatLabo.objects.filter(
        prescription__date_prescription__date__gte=debut,
        prescription__date_prescription__date__lte=fin,
        statut='VALIDE'
    ).filter(
        Q(echantillon_1__in=BAAR_POS) | Q(echantillon_2__in=BAAR_POS) | Q(resultat_genexpert__in=GENE_POS)
    )
    if unite:
        resultats_positifs = resultats_positifs.filter(prescription__patient__traitement__unite_traitement=unite)
    nb_tpm_plus = resultats_positifs.values('prescription__patient').distinct().count()
    taux_positivite = round((nb_tpm_plus / nb_suspects * 100), 1) if nb_suspects else 0.0

    # Nouveaux cas TPM+ : Traitement NOUVEAU + patient avec positif diagnostic dans période
    # On filtre traitement par date_debut dans période
    traitements = Traitement.objects.filter(date_debut__gte=debut, date_debut__lte=fin)
    if unite:
        traitements = traitements.filter(unite_traitement=unite)
    nouveaux = traitements.filter(type_cas=TypeCasTraitement.NOUVEAU)
    # Pour TPM+ / TPM- on regarde résultat diagnostic du patient
    nb_nouveaux_tpm_plus = 0
    nb_nouveaux_tpm_moins = 0
    for t in nouveaux.select_related('patient'):
        # dernier résultat diagnostic positif ?
        has_positive = ResultatLabo.objects.filter(
            prescription__patient=t.patient,
            prescription__motif=MotifExamen.DIAGNOSTIC,
            statut='VALIDE'
        ).filter(
            Q(echantillon_1__in=BAAR_POS) | Q(echantillon_2__in=BAAR_POS) | Q(resultat_genexpert__in=GENE_POS)
        ).exists()
        if has_positive:
            nb_nouveaux_tpm_plus += 1
        else:
            # Vérifie si au moins un examen diagnostic existe (sinon on ne compte pas comme TPM- ?)
            has_diag = ExamenPrescription.objects.filter(patient=t.patient, motif=MotifExamen.DIAGNOSTIC).exists()
            if has_diag:
                nb_nouveaux_tpm_moins += 1

    nb_retraitement = traitements.filter(type_cas=TypeCasTraitement.RECHUTE).count()

    return {
        'nb_suspects': nb_suspects,
        'taux_positivite': taux_positivite,
        'nb_nouveaux_tpm_plus': nb_nouveaux_tpm_plus,
        'nb_nouveaux_tpm_moins': nb_nouveaux_tpm_moins,
        'nb_retraitement': nb_retraitement,
        'taux_notification': None,  # N/A - population non modélisée
    }


def indicateurs_resultats_traitement(debut, fin, unite=None):
    """Cohorte trimestrielle : issue finale des traitements dont date_debut dans période."""
    qs = Traitement.objects.filter(date_debut__gte=debut, date_debut__lte=fin)
    if unite:
        qs = qs.filter(unite_traitement=unite)
    total = qs.count()
    gueris = qs.filter(issue_finale=IssueFinale.GUERI).count()
    termines = qs.filter(issue_finale=IssueFinale.TERMINE).count()
    echecs = qs.filter(issue_finale=IssueFinale.ECHEC).count()
    pdv = qs.filter(issue_finale=IssueFinale.PERDU_DE_VUE).count()
    decedes = qs.filter(issue_finale=IssueFinale.DECEDE).count()
    transferes = qs.filter(issue_finale=IssueFinale.TRANSFERE).count()

    def pct(n): return round((n / total * 100), 1) if total else 0.0

    succes = gueris + termines
    return {
        'total': total,
        'gueris': gueris,
        'termines': termines,
        'echecs': echecs,
        'pdv': pdv,
        'decedes': decedes,
        'transferes': transferes,
        'taux_succes': pct(succes),
        'taux_guerison': pct(gueris),
        'taux_echec': pct(echecs),
        'taux_abandon': pct(pdv),
        'taux_deces': pct(decedes),
    }


def indicateurs_laboratoire(debut, fin, unite=None):
    # frottis diagnostic : prescriptions BACILLOSCOPIE + motif DIAGNOSTIC
    base = ExamenPrescription.objects.filter(date_prescription__date__gte=debut, date_prescription__date__lte=fin)
    if unite:
        base = base.filter(patient__traitement__unite_traitement=unite)
    try:
        bac_code = TypeExamen.objects.get(code='BACILLOSCOPIE')
        frottis_diag_qs = base.filter(examens=bac_code, motif=MotifExamen.DIAGNOSTIC)
        nb_frottis_diag = frottis_diag_qs.count() * 2  # 2 lames par suspect
    except TypeExamen.DoesNotExist:
        nb_frottis_diag = base.filter(motif=MotifExamen.DIAGNOSTIC).count() * 2

    try:
        bac_code = TypeExamen.objects.get(code='BACILLOSCOPIE')
        frottis_ctrl_qs = base.filter(examens=bac_code, motif=MotifExamen.SUIVI_CONTROLE).filter(mois_controle__in=[MoisControle.C2, MoisControle.C5, MoisControle.FIN])
        nb_frottis_controle = frottis_ctrl_qs.count() * 1  # 1 lame par contrôle ? On compte 1 par demande
    except:
        nb_frottis_controle = base.filter(motif=MotifExamen.SUIVI_CONTROLE).count()

    # Taux conversion C2
    # TPM+ initiaux dans période : distinct patients avec diag positif
    BAAR_POS = list(ResultatLabo.BAAR_POSITIFS)
    GENE_POS = [ResultatGeneXpert.MTB_PLUS_RIF_PLUS, ResultatGeneXpert.MTB_PLUS_RIF_MOINS, ResultatGeneXpert.MTB_MOINS_RIF_PLUS]
    tpm_plus_patients = set(
        ResultatLabo.objects.filter(
            prescription__motif=MotifExamen.DIAGNOSTIC,
            prescription__date_prescription__date__gte=debut,
            prescription__date_prescription__date__lte=fin,
            statut='VALIDE'
        ).filter(
            Q(echantillon_1__in=BAAR_POS) | Q(echantillon_2__in=BAAR_POS) | Q(resultat_genexpert__in=GENE_POS)
        ).values_list('prescription__patient_id', flat=True).distinct()
    )
    # Parmi eux, ceux contrôlés à C2
    c2_prescriptions = ExamenPrescription.objects.filter(
        mois_controle=MoisControle.C2,
        motif=MotifExamen.SUIVI_CONTROLE,
        date_prescription__date__gte=debut,
        date_prescription__date__lte=fin
    )
    if unite:
        c2_prescriptions = c2_prescriptions.filter(patient__traitement__unite_traitement=unite)
    c2_controles = 0
    c2_negatives = 0
    for pres in c2_prescriptions.select_related('patient'):
        if pres.patient_id not in tpm_plus_patients:
            continue
        c2_controles += 1
        res = pres.resultat_valide
        if res and res.echantillon_1 == ResultatBacilloscopie.NEGATIF and res.echantillon_2 == ResultatBacilloscopie.NEGATIF:
            # GeneXpert non pertinent pour conversion bacillaire, on ne considère que BAAR
            c2_negatives += 1
        elif res and res.echantillon_1 == ResultatBacilloscopie.NEGATIF and not res.echantillon_2:
            c2_negatives += 1

    taux_conversion = round((c2_negatives / c2_controles * 100), 1) if c2_controles else 0.0

    # Cultures et DST
    try:
        culture = TypeExamen.objects.get(code='CULTURE')
        nb_cultures = base.filter(examens=culture).count()
    except:
        nb_cultures = 0

    return {
        'nb_frottis_diag': nb_frottis_diag,
        'nb_frottis_controle': nb_frottis_controle,
        'taux_conversion_c2': taux_conversion,
        'nb_cultures_dst': nb_cultures,
        'cq': None,  # N/A
    }


def indicateurs_communautaire(debut, fin, unite=None):
    qs = Traitement.objects.filter(date_debut__gte=debut, date_debut__lte=fin)
    if unite:
        qs = qs.filter(unite_traitement=unite)
    # DOTS communautaire : au moins une observance J
    asc_patients = set(
        ObservanceJournaliere.objects.filter(
            traitement__in=qs,
            statut=ModeObservation.RELAIS_COMMUNAUTAIRE
        ).values_list('traitement_id', flat=True).distinct()
    )
    nb_asc = len(asc_patients)
    nb_asc_gueris = Traitement.objects.filter(id__in=asc_patients, issue_finale=IssueFinale.GUERI).count() if nb_asc else 0
    taux_succes_asc = round((nb_asc_gueris / nb_asc * 100), 1) if nb_asc else 0.0

    return {
        'nb_suspects_referes_asc': None,  # N/A
        'nb_dots_communautaire': nb_asc,
        'taux_succes_asc': taux_succes_asc,
    }


def indicateurs_population_risque(debut, fin, unite=None):
    qs = Traitement.objects.filter(date_debut__gte=debut, date_debut__lte=fin)
    if unite:
        qs = qs.filter(unite_traitement=unite)
    total = qs.count()
    # pédiatrique <15 ans
    nb_pediatrique = 0
    for t in qs.select_related('patient'):
        age = t.patient.age
        if age is not None and age < 15:
            nb_pediatrique += 1
    taux_pediatrique = round((nb_pediatrique / total * 100), 1) if total else 0.0
    return {
        'nb_prison': None,
        'nb_contacts_examines': None,
        'nb_enfants_inh': None,
        'nb_pediatrique': nb_pediatrique,
        'taux_pediatrique': taux_pediatrique,
    }


def liste_unites():
    return list(Traitement.objects.values_list('unite_traitement', flat=True).distinct().order_by('unite_traitement'))


def build_dashboard_context(debut, fin, unite=None):
    return {
        'epi': indicateurs_epidemiologiques(debut, fin, unite),
        'cohorte': indicateurs_resultats_traitement(debut, fin, unite),
        'labo': indicateurs_laboratoire(debut, fin, unite),
        'commu': indicateurs_communautaire(debut, fin, unite),
        'risque': indicateurs_population_risque(debut, fin, unite),
        'vih': {
            'couverture_vih': None,
            'taux_coinfection': None,
            'ctx': None,
            'arv': None,
        },
        'pharma': {
            'rupture': None,
            'securite': None,
            'perimes': None,
        },
    }
