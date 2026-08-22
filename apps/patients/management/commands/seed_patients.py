# pyrefly: ignore [missing-import]
import calendar
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.patients.models import (
    ApparenceEchantillon,
    CategorieSchemaTraitement,
    DecisionDiagnostic,
    ExamenPrescription,
    HistoriqueModificationTraitement,
    InterpretationResultat,
    IssueFinale,
    ModeObservation,
    ModificationPatient,
    MoisControle,
    MotifExamen,
    NatureEchantillon,
    ObservanceJournaliere,
    Patient,
    RendezVous,
    ResultatBacilloscopie,
    ResultatGeneXpert,
    ResultatLabo,
    SchemaTraitement,
    Sexe,
    StatutDossier,
    StatutExamen,
    StatutRendezVous,
    StatutResultat,
    StatutTraitement,
    TechniqueColoration,
    Traitement,
    TypeCasTraitement,
    TypeExamen,
    TypeModificationTraitement,
    TypeRendezVous,
    VerrouDossier,
    VisiteSuivi,
)
from apps.patients.services import BANDES_POSOLOGIE, calculer_posologie
from apps.users.models import CustomUser, UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOMS = [
    "Kalombo", "Nzuzi", "Ilunga", "Mputu", "Bongoy", "Bakala", "Mavungu",
    "Mokolo", "Kanza", "Kabasele", "Mbala", "Kabongo", "Tshisekedi",
    "Lumumba", "Kasongo", "Mbuyi", "Mwamba", "Ngoy", "Kanku", "Musangu",
    "Kabeya", "Tshibanda", "Mutombo", "Kayembe", "Kazadi", "Mbuyi",
    "Ngalula", "Ntumba", "Mulamba", "Kabasele", "Mwanza", "Kibonge",
]
PRENOMS_M = [
    "Paul", "Jean", "Pierre", "Joseph", "Jacques", "Emmanuel", "Serge",
    "Albert", "Didier", "Eric", "Josué", "Patrick", "Benjamin", "Samuel",
    "David", "Moise", "Daniel", "Christian", "Felix", "Dieudonné",
    "Gauthier", "Olivier", "Herve", "Cedric", "Tresor", "Jonathan",
]
PRENOMS_F = [
    "Marthe", "Marie", "Grace", "Nadine", "Judith", "Gisele", "Chantal",
    "Brigitte", "Antoinette", "Francine", "Christelle", "Deborah",
    "Priscille", "Noella", "Clarisse", "Bijou", "Mireille", "Esther",
    "Rachel", "Sarah", "Aline", "Fifi", "Mado", "Solange", "Henriette",
]
POST_NOMS = [
    "Kanyinda", "Mbuyi", "Kayembe", "Kazadi", "Kabeya", "Tshibanda",
    "Ntumba", "Mukendi", "Kabongo", "Mutombo", "Ngalula", "Mulamba",
    "", "", "", "",  # 40% vide
]
DISTRICTS = ["Mont-Ngafula", "Ngaliema", "Selembao", "Bumbu", "Makala", "Ngaba", "Lemba", "Matete", "Kalamu", "Limete", "Kinshasa", "Gombe", "Barumbu"]
SECTEURS = ["Secteur Météo", "Secteur ELK", "Secteur Mangulu", "Secteur Benga", "Secteur Centre", "Secteur Kasa-Vubu", ""]
CELLULES = ["Cellule A", "Cellule B", "Cellule C", "Cellule D", ""]
VILLAGES = ["Village Turc", "Village Kindele", "Village Sebo", "Village Mabala", "Camp Luka", ""]
UNITES = ["HGR Makala"]
ORGANES_EP = ["ganglion cervical", "plèvre", "péritoine", "os vertébral", "rein", "méninges", "péritoine", "peau"]
TYPES_EXAMEN_CODES = ["BACILLOSCOPIE", "GENEXPERT", "CULTURE", "DST"]


def random_phone():
    return f"+243 8{random.randint(1,9)} {random.randint(100,999)} {random.randint(1000,9999)}"


def random_date_in_year(year: int) -> date:
    month = random.randint(1, 12)
    _, last = calendar.monthrange(year, month)
    day = random.randint(1, last)
    return date(year, month, day)


def random_cree_le_datetime(base_date: date) -> datetime:
    # Random hour 07-17, minute 0-59, aware in Africa/Kinshasa
    t = time(random.randint(7, 17), random.randint(0, 59), random.randint(0, 59))
    naive = datetime.combine(base_date, t)
    # make aware
    if timezone.is_naive(naive):
        return timezone.make_aware(naive)
    return naive


def pick_type_cas() -> str:
    return TypeCasTraitement.RECHUTE if random.random() < 0.15 else TypeCasTraitement.NOUVEAU


def pick_issue_finale_for_bucket(bucket: str):
    mapping = {
        "GUERI": IssueFinale.GUERI,
        "TERMINE": IssueFinale.TERMINE,
        "ECHEC": IssueFinale.ECHEC,
        "DECEDE": IssueFinale.DECEDE,
        "PERDU_DE_VUE": IssueFinale.PERDU_DE_VUE,
        "TRANSFERE": IssueFinale.TRANSFERE,
    }
    return mapping.get(bucket)


def generate_poids(age: int) -> Decimal | None:
    if random.random() < 0.03:
        return None  # 3% sans poids
    if age is not None and age < 15:
        w = random.uniform(16, 45)
    elif age is not None and age > 60:
        w = random.uniform(48, 85)
    else:
        w = random.uniform(32, 95)
    # force some edge values for posologie bands
    r = random.random()
    if r < 0.06:
        w = random.uniform(28, 29.9)  # hors bande <30
    elif r < 0.10:
        w = random.uniform(30, 38)
    elif r < 0.15:
        w = random.uniform(71, 90)
    return Decimal(str(round(w, 1)))


def generate_age(bucket: str, base_date: date) -> tuple[date, int]:
    # distribution: <15 8%, 15-24 15%, 25-60 60%, >60 17%
    r = random.random()
    if r < 0.08:
        age = random.randint(2, 14)
    elif r < 0.23:
        age = random.randint(15, 24)
    elif r < 0.83:
        age = random.randint(25, 60)
    else:
        age = random.randint(61, 82)
    # perturb for edge
    dob = date(base_date.year - age, random.randint(1, 12), random.randint(1, 28))
    # fix feb 29 issues already via day 1-28
    return dob, age


def choose_exam_codes_for_diag() -> list[str]:
    r = random.random()
    if r < 0.20:
        return ["BACILLOSCOPIE"]
    if r < 0.40:
        return ["GENEXPERT"]
    if r < 0.80:
        return ["BACILLOSCOPIE", "GENEXPERT"]
    if r < 0.90:
        return ["BACILLOSCOPIE", "GENEXPERT", "CULTURE"]
    if r < 0.95:
        return ["CULTURE", "DST"]
    return ["BACILLOSCOPIE", "CULTURE", "DST"]


def choose_exam_codes_for_suivi() -> list[str]:
    r = random.random()
    if r < 0.60:
        return ["BACILLOSCOPIE"]
    if r < 0.80:
        return ["BACILLOSCOPIE", "GENEXPERT"]
    if r < 0.90:
        return ["CULTURE"]
    return ["BACILLOSCOPIE", "GENEXPERT", "CULTURE"]


class Command(BaseCommand):
    help = "Seed 1000 patients répartis sur 5 années, couvrant tous les cas métier (idempotent avec --clear)."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=1000, help="Nombre de patients à générer (défaut 1000)")
        parser.add_argument("--clear", action="store_true", help="Supprime les patients existants avant seed")
        parser.add_argument("--seed", type=int, default=42, help="Seed aléatoire pour reproductibilité")

    def handle(self, *args, **options):
        count = options["count"]
        do_clear = options["clear"]
        seed = options["seed"]

        random.seed(seed)

        self.stdout.write(f"Seed patients: count={count}, clear={do_clear}, seed={seed}")

        # Ensure reference data exists
        schemas = {s.code: s for s in SchemaTraitement.objects.all()}
        if not schemas:
            self.stderr.write("Aucun SchemaTraitement trouvé — exécutez les migrations.")
            return
        type_examens = {t.code: t for t in TypeExamen.objects.all()}
        if not type_examens:
            self.stderr.write("Aucun TypeExamen trouvé — exécutez les migrations.")
            return

        # Ensure demo users
        medecins = list(CustomUser.objects.filter(role=UserRole.MEDECIN, is_active=True))
        infirmiers = list(CustomUser.objects.filter(role=UserRole.INFIRMIER, is_active=True))
        laborantins = list(CustomUser.objects.filter(role=UserRole.LABORANTIN, is_active=True))
        if not medecins or not infirmiers or not laborantins:
            self.stdout.write("Utilisateurs demo manquants — création via seed_demo_users...")
            from django.core.management import call_command
            call_command("seed_demo_users")
            medecins = list(CustomUser.objects.filter(role=UserRole.MEDECIN, is_active=True))
            infirmiers = list(CustomUser.objects.filter(role=UserRole.INFIRMIER, is_active=True))
            laborantins = list(CustomUser.objects.filter(role=UserRole.LABORANTIN, is_active=True))

        # Years distribution : 2021-2025
        years = [2021, 2022, 2023, 2024, 2025]
        # exact counts for 1000 -> 160,180,200,220,240
        if count == 1000:
            per_year_counts = {2021: 160, 2022: 180, 2023: 200, 2024: 220, 2025: 240}
        else:
            # proportional
            weights = [0.16, 0.18, 0.20, 0.22, 0.24]
            per_year_counts = {}
            remaining = count
            for idx, y in enumerate(years):
                if idx == len(years) - 1:
                    per_year_counts[y] = remaining
                else:
                    c = int(round(count * weights[idx]))
                    per_year_counts[y] = c
                    remaining -= c
            # adjust if sum != count
            diff = count - sum(per_year_counts.values())
            per_year_counts[years[-1]] += diff

        years_list = []
        for y in years:
            years_list.extend([y] * per_year_counts[y])
        random.shuffle(years_list)

        # Status distribution buckets
        # We need exactly count items covering all statuses
        if count == 1000:
            bucket_counts = {
                "PROVISOIRE": 30,
                "CONFIRME": 20,
                "NON_CONFIRME": 150,
                "EN_TRAITEMENT": 300,
                "GUERI": 280,
                "TERMINE": 80,
                "ECHEC": 40,
                "DECEDE": 40,
                "PERDU_DE_VUE": 35,
                "TRANSFERE": 25,
            }
        else:
            # scale proportionally
            base = {
                "PROVISOIRE": 0.03, "CONFIRME": 0.02, "NON_CONFIRME": 0.15,
                "EN_TRAITEMENT": 0.30, "GUERI": 0.28, "TERMINE": 0.08,
                "ECHEC": 0.04, "DECEDE": 0.04, "PERDU_DE_VUE": 0.035, "TRANSFERE": 0.025,
            }
            bucket_counts = {}
            remaining = count
            keys = list(base.keys())
            for k in keys[:-1]:
                c = int(round(count * base[k]))
                bucket_counts[k] = c
                remaining -= c
            bucket_counts[keys[-1]] = remaining
            # fix negative
            if bucket_counts[keys[-1]] < 0:
                bucket_counts[keys[-1]] = 0

        statuses_list = []
        for bucket, cnt in bucket_counts.items():
            statuses_list.extend([bucket] * cnt)
        # ensure len == count
        if len(statuses_list) < count:
            statuses_list.extend(["EN_TRAITEMENT"] * (count - len(statuses_list)))
        elif len(statuses_list) > count:
            statuses_list = statuses_list[:count]
        random.shuffle(statuses_list)

        # NDP / DM counters per year (continue from existing)
        ndp_counters: dict[int, int] = {}
        dm_counters: dict[int, int] = {}
        for y in years:
            prefix_ndp = f"NDP-{y}-"
            last_ndp = Patient.objects.filter(ndp__startswith=prefix_ndp).order_by("-ndp").values_list("ndp", flat=True).first()
            ndp_counters[y] = int(last_ndp.rsplit("-", 1)[1]) if last_ndp else 0
            prefix_dm = f"DM-{y}-"
            last_dm = ExamenPrescription.objects.filter(numero_demande__startswith=prefix_dm).order_by("-numero_demande").values_list("numero_demande", flat=True).first()
            dm_counters[y] = int(last_dm.rsplit("-", 1)[1]) if last_dm else 0

        # Clear if requested
        if do_clear:
            self.stdout.write("Clearing existing patients and linked data...")
            with transaction.atomic():
                from django.db import connection
                # legacy tables from old app structure (appointments_*, treatment_*)
                with connection.cursor() as cur:
                    for tbl in ("appointments_rendezvous", "treatment_visitecontrole", "treatment_modificationtraitement", "treatment_traitement"):
                        try:
                            cur.execute(f'DELETE FROM "{tbl}"')
                        except Exception:
                            pass
                # delete in FK-safe order
                ObservanceJournaliere.objects.all().delete()
                VisiteSuivi.objects.all().delete()
                HistoriqueModificationTraitement.objects.all().delete()
                RendezVous.objects.all().delete()
                ResultatLabo.objects.all().delete()
                InterpretationResultat.objects.all().delete()
                ExamenPrescription.objects.all().delete()
                Traitement.objects.all().delete()
                ModificationPatient.objects.all().delete()
                VerrouDossier.objects.all().delete()
                # Notifications are user-linked, keep or clear seed-related? clear all for cleanliness
                from apps.patients.models import Notification
                Notification.objects.all().delete()
                Patient.objects.all().delete()
                # reset counters after clear
                for y in years:
                    ndp_counters[y] = 0
                    dm_counters[y] = 0
            self.stdout.write(self.style.SUCCESS("Clear done."))

        # Track used RDV slots to test conflict
        rdv_slots: set[tuple[date, time]] = set()
        # Pre-fill with existing slots if not clear
        if not do_clear:
            for dt, hr in RendezVous.objects.filter(statut=StatutRendezVous.PLANIFIE).values_list("date", "heure"):
                rdv_slots.add((dt, hr))

        created = 0
        for idx in range(count):
            with transaction.atomic():
                year = years_list[idx]
                bucket = statuses_list[idx]  # final bucket

                base_date = random_date_in_year(year)
                cree_le_dt = random_cree_le_datetime(base_date)

                sexe = random.choice([Sexe.MASCULIN, Sexe.FEMININ])
                if sexe == Sexe.MASCULIN:
                    prenom = random.choice(PRENOMS_M)
                else:
                    prenom = random.choice(PRENOMS_F)
                nom = random.choice(NOMS)
                post_nom = random.choice(POST_NOMS)
                dob, age = generate_age(bucket, base_date)
                poids = generate_poids(age)

                district = random.choice(DISTRICTS)
                secteur = random.choice(SECTEURS)
                cellule = random.choice(CELLULES)
                village = random.choice(VILLAGES)
                telephone = random_phone() if random.random() < 0.85 else ""

                # signes
                signes = {
                    "signe_toux_persistante": random.random() < 0.70,
                    "signe_fievre_sueurs": random.random() < 0.50,
                    "signe_perte_poids": random.random() < 0.45,
                    "signe_hemoptysie": random.random() < 0.15,
                    "signe_contact_cas_tpm": random.random() < 0.20,
                }
                comorbs = {
                    "comorb_diabete": random.random() < 0.12,
                    "comorb_malnutrition": random.random() < 0.18,
                    "comorb_autre": random.random() < 0.08,
                }
                autres_comorb = "Drépanocytose" if comorbs["comorb_autre"] and random.random() < 0.5 else ("HTA" if comorbs["comorb_autre"] else "")
                observations = random.choice(["", "", "Cicatrice BCG présente.", "Dyspnée modérée.", "AEG, asthénie."])

                # type_cas & schema
                type_cas = pick_type_cas()
                categorie = CategorieSchemaTraitement.RETRAITEMENT if type_cas == TypeCasTraitement.RECHUTE else CategorieSchemaTraitement.NOUVEAU_CAS
                # find schema by categorie
                if categorie == CategorieSchemaTraitement.RETRAITEMENT:
                    schema = schemas.get("2SRHZE/1RHZE/5RHE") or next(s for s in schemas.values() if s.categorie == categorie)
                else:
                    schema = schemas.get("2RHZE/4RH") or next(s for s in schemas.values() if s.categorie == categorie)

                posologie = calculer_posologie(poids)
                unite = random.choice(UNITES)

                ndp_counters[year] += 1
                ndp = f"NDP-{year}-{ndp_counters[year]:04d}"

                medecin = random.choice(medecins)
                infirmier = random.choice(infirmiers)
                laborantin = random.choice(laborantins)

                # Create Patient with provisional status first
                patient = Patient(
                    ndp=ndp,
                    nom=nom,
                    post_nom=post_nom,
                    prenom=prenom,
                    sexe=sexe,
                    date_naissance=dob,
                    district=district,
                    secteur=secteur,
                    cellule=cellule,
                    village=village,
                    telephone=telephone,
                    poids=poids,
                    **signes,
                    **comorbs,
                    autres_comorbidites=autres_comorb,
                    observations_cliniques=observations,
                    statut=StatutDossier.PROVISOIRE,
                    cree_par=medecin,
                )
                patient.save()
                # override cree_le to historic date
                Patient.objects.filter(pk=patient.pk).update(cree_le=cree_le_dt)
                patient.refresh_from_db()

                # Create Traitement
                traitement = Traitement(
                    patient=patient,
                    schema=schema,
                    type_cas=type_cas,
                    date_debut=base_date,
                    poids_initial=poids,
                    posologie_jour=posologie,
                    unite_traitement=unite,
                    statut=StatutTraitement.EN_COURS,
                    cree_par=medecin,
                )
                traitement.save()

                # ------------------------------------------------------------------
                # Workflow per bucket
                # ------------------------------------------------------------------
                # Helper to create prescription
                def create_prescription(motif, nature, mois_ctrl, codes, base_dt, organe=""):
                    dm_year = base_dt.year
                    # ensure counter exists for that year
                    if dm_year not in dm_counters:
                        dm_counters[dm_year] = 0
                        # check existing max
                        prefix = f"DM-{dm_year}-"
                        last = ExamenPrescription.objects.filter(numero_demande__startswith=prefix).order_by("-numero_demande").values_list("numero_demande", flat=True).first()
                        if last:
                            dm_counters[dm_year] = int(last.rsplit("-", 1)[1])
                    dm_counters[dm_year] += 1
                    numero = f"DM-{dm_year}-{dm_counters[dm_year]:04d}"
                    if isinstance(base_dt, datetime):
                        base_d = base_dt.date()
                    else:
                        base_d = base_dt
                    pres = ExamenPrescription(
                        numero_demande=numero,
                        patient=patient,
                        medecin=medecin,
                        nature_echantillon=nature,
                        organe=organe,
                        motif=motif,
                        mois_controle=mois_ctrl,
                        date_prelevement=base_d + timedelta(days=1),
                        observations="",
                        statut=StatutExamen.EN_ATTENTE,
                    )
                    pres.save()
                    # set exams
                    exam_objs = [type_examens[c] for c in codes if c in type_examens]
                    pres.examens.set(exam_objs)
                    # override date_prescription
                    if isinstance(base_dt, datetime):
                        dt_pres = base_dt
                    else:
                        # combine with random time 08-11
                        t = time(random.randint(8, 11), random.randint(0, 59))
                        naive = datetime.combine(base_d, t)
                        dt_pres = timezone.make_aware(naive) if timezone.is_naive(naive) else naive
                    ExamenPrescription.objects.filter(pk=pres.pk).update(date_prescription=dt_pres)
                    pres.refresh_from_db()
                    return pres

                def create_resultat(prescription, is_positive: bool, base_dt):
                    # base_dt is prescription date
                    if isinstance(base_dt, datetime):
                        base_d = base_dt.date()
                    else:
                        base_d = base_dt
                    date_recep = base_d + timedelta(days=random.randint(1, 3))
                    date_lect = timezone.make_aware(datetime.combine(date_recep, time(random.randint(9, 16), random.randint(0, 59))))
                    # if prescription has bacilloscopie
                    codes = set(prescription.examens.values_list("code", flat=True))
                    has_bac = "BACILLOSCOPIE" in codes
                    has_gx = "GENEXPERT" in codes

                    # defaults
                    e1 = ""
                    e2 = ""
                    tech = ""
                    appar = ""
                    gene = ""
                    if has_bac:
                        appar = random.choice(list(ApparenceEchantillon.values))
                        tech = random.choice(list(TechniqueColoration.values))
                        if is_positive:
                            # 70% both positive, 30% one positive
                            pos_choices = [ResultatBacilloscopie.POSITIF_1, ResultatBacilloscopie.POSITIF_2, ResultatBacilloscopie.POSITIF_3, ResultatBacilloscopie.BAAR_1_9]
                            if random.random() < 0.7:
                                e1 = random.choice(pos_choices)
                                e2 = random.choice(pos_choices)
                            else:
                                e1 = random.choice(pos_choices)
                                e2 = ResultatBacilloscopie.NEGATIF
                        else:
                            e1 = ResultatBacilloscopie.NEGATIF
                            e2 = ResultatBacilloscopie.NEGATIF if random.random() < 0.8 else random.choice([ResultatBacilloscopie.NEGATIF, ""])
                    if has_gx:
                        if is_positive:
                            gene = random.choice([ResultatGeneXpert.MTB_PLUS_RIF_PLUS, ResultatGeneXpert.MTB_PLUS_RIF_MOINS])
                            # 10% rif+
                            if random.random() < 0.1:
                                gene = ResultatGeneXpert.MTB_PLUS_RIF_PLUS
                        else:
                            gene = random.choice([ResultatGeneXpert.NON_FAIT, ResultatGeneXpert.INVALID, ResultatGeneXpert.NON_FAIT])
                            # for true negative, NON_FAIT is most common
                            if random.random() < 0.7:
                                gene = ResultatGeneXpert.NON_FAIT

                    res = ResultatLabo(
                        prescription=prescription,
                        laborantin=laborantin,
                        statut=StatutResultat.VALIDE,
                        date_reception=date_recep,
                        date_lecture=date_lect,
                        apparence=appar if has_bac else "",
                        echantillon_1=e1 if has_bac else "",
                        echantillon_2=e2 if has_bac else "",
                        technique_coloration=tech if has_bac else "",
                        resultat_genexpert=gene if has_gx else "",
                        commentaires=random.choice(["", "", "Qualité suffisante.", "Échantillon mucopurulent.", "Contamination mineure."]),
                    )
                    res.save()
                    # update prescription statut
                    prescription.statut = StatutExamen.RESULTATS_DISPONIBLES
                    prescription.save(update_fields=["statut"])
                    return res

                # --------------------------------------------------------------
                # Branch logic
                # --------------------------------------------------------------
                if bucket == "PROVISOIRE":
                    # One pending prescription, no result
                    nature = NatureEchantillon.PULMONAIRE if signes["signe_toux_persistante"] or signes["signe_hemoptysie"] else random.choice([NatureEchantillon.PULMONAIRE, NatureEchantillon.EXTRA_PULMONAIRE])
                    organe = random.choice(ORGANES_EP) if nature == NatureEchantillon.EXTRA_PULMONAIRE else ""
                    codes = choose_exam_codes_for_diag()
                    pres_dt = cree_le_dt + timedelta(days=random.randint(0, 5))
                    pres = create_prescription(MotifExamen.DIAGNOSTIC, nature, "", codes, pres_dt, organe)
                    # keep status EN_ATTENTE, no result, no interpretation
                    patient.statut = StatutDossier.PROVISOIRE
                    patient.save(update_fields=["statut"])

                elif bucket == "CONFIRME":
                    # Positive diag but not yet admitted (CONFIRME waiting for infirmier)
                    nature = NatureEchantillon.PULMONAIRE
                    codes = choose_exam_codes_for_diag()
                    pres_dt = cree_le_dt + timedelta(days=random.randint(0, 3))
                    pres = create_prescription(MotifExamen.DIAGNOSTIC, nature, "", codes, pres_dt)
                    res = create_resultat(pres, is_positive=True, base_dt=pres_dt)
                    # interpretation CONFIRMEE
                    interp_dt = res.date_lecture + timedelta(days=random.randint(1, 3))
                    InterpretationResultat.objects.create(
                        prescription=pres,
                        medecin=medecin,
                        observations="Analyse clinique concordante.",
                        interpretation="Tuberculose pulmonaire confirmée par bacilloscopie/GeneXpert.",
                        decision=DecisionDiagnostic.CONFIRMEE,
                    )
                    # set cree_le historic? auto_now_add, override via update
                    ir = InterpretationResultat.objects.filter(prescription=pres).first()
                    InterpretationResultat.objects.filter(pk=ir.pk).update(cree_le=interp_dt)
                    patient.statut = StatutDossier.CONFIRME
                    patient.save(update_fields=["statut"])
                    # No admission

                elif bucket == "NON_CONFIRME":
                    nature = NatureEchantillon.PULMONAIRE
                    codes = choose_exam_codes_for_diag()
                    pres_dt = cree_le_dt + timedelta(days=random.randint(0, 3))
                    pres = create_prescription(MotifExamen.DIAGNOSTIC, nature, "", codes, pres_dt)
                    res = create_resultat(pres, is_positive=False, base_dt=pres_dt)
                    interp_dt = res.date_lecture + timedelta(days=random.randint(1, 3))
                    InterpretationResultat.objects.create(
                        prescription=pres,
                        medecin=medecin,
                        observations="Clinique non évocatrice, résultats négatifs.",
                        interpretation="Tuberculose infirmée — diagnostic négatif.",
                        decision=DecisionDiagnostic.INFIRMEE,
                    )
                    ir = InterpretationResultat.objects.filter(prescription=pres).first()
                    InterpretationResultat.objects.filter(pk=ir.pk).update(cree_le=interp_dt)
                    patient.statut = StatutDossier.NON_CONFIRME
                    patient.save(update_fields=["statut"])
                    # No admission, but test that admission blocked

                else:
                    # All other buckets are admitted (EN_TRAITEMENT + closed)
                    # Step: positive diag -> confirmed -> admission
                    nature = NatureEchantillon.PULMONAIRE if random.random() < 0.85 else NatureEchantillon.EXTRA_PULMONAIRE
                    organe = random.choice(ORGANES_EP) if nature == NatureEchantillon.EXTRA_PULMONAIRE else ""
                    codes = choose_exam_codes_for_diag()
                    pres_dt = cree_le_dt + timedelta(days=random.randint(0, 4))
                    pres = create_prescription(MotifExamen.DIAGNOSTIC, nature, "", codes, pres_dt, organe)
                    res = create_resultat(pres, is_positive=True, base_dt=pres_dt)
                    interp_dt = res.date_lecture + timedelta(days=random.randint(1, 4))
                    InterpretationResultat.objects.create(
                        prescription=pres,
                        medecin=medecin,
                        observations="Tableau clinique évocateur, confirmation biologique.",
                        interpretation="Tuberculose confirmée, traitement indiqué.",
                        decision=DecisionDiagnostic.CONFIRMEE,
                    )
                    ir = InterpretationResultat.objects.filter(prescription=pres).first()
                    InterpretationResultat.objects.filter(pk=ir.pk).update(cree_le=interp_dt)

                    # Admission
                    adm_dt = timezone.make_aware(datetime.combine((interp_dt.date() + timedelta(days=random.randint(1, 7))), time(random.randint(8, 14), random.randint(0, 59))))
                    # Random admin fields tweak 30% chance
                    if random.random() < 0.3:
                        # create modification trail
                        old_tel = patient.telephone
                        new_tel = random_phone()
                        ModificationPatient.objects.create(patient=patient, auteur=infirmier, champ="telephone", ancienne_valeur=old_tel, nouvelle_valeur=new_tel)
                        patient.telephone = new_tel
                    patient.date_admission = adm_dt
                    patient.admise_par = infirmier
                    # for EN_TRAITEMENT bucket stay EN_TRAITEMENT, for closed will be updated later after cloture
                    patient.statut = StatutDossier.EN_TRAITEMENT
                    patient.save()

                    # ----------------------------------------------------------
                    # Add observance, visites, RDV etc for admitted
                    # ----------------------------------------------------------
                    total_mois = traitement.schema.duree_totale_mois
                    # Observance generation
                    # For closed patients: good adherence except ECHEC/PERDU_DE_VUE
                    # For EN_TRAITEMENT: partial
                    is_closed_bucket = bucket in ("GUERI", "TERMINE", "ECHEC", "DECEDE", "PERDU_DE_VUE", "TRANSFERE")
                    # Determine months to fill
                    # For DECEDE: early death 1-3 months; for TRANSFERE: 1-4 months
                    max_mois_to_fill = total_mois
                    if bucket == "DECEDE":
                        max_mois_to_fill = random.randint(1, 3)
                    elif bucket == "TRANSFERE":
                        max_mois_to_fill = random.randint(2, 4)
                    elif bucket == "PERDU_DE_VUE" and not is_closed_bucket:
                        pass
                    # Generate observance per month
                    for mois in range(1, max_mois_to_fill + 1):
                        # decide adherence level
                        if bucket == "GUERI":
                            adherence = 0.92
                        elif bucket == "TERMINE":
                            adherence = 0.88
                        elif bucket == "ECHEC":
                            adherence = 0.65
                        elif bucket == "PERDU_DE_VUE":
                            # will simulate absence after some point
                            adherence = 0.40 if mois > 2 else 0.85
                        elif bucket == "EN_TRAITEMENT":
                            adherence = 0.80 if random.random() < 0.7 else 0.50
                        else:
                            adherence = 0.75

                        # For EN_TRAITEMENT from old years we want some lost: leave recent months empty to trigger perdu_de_vue
                        # If year < 2024 and EN_TRAITEMENT, simulate no prise for last 3 months
                        if bucket == "EN_TRAITEMENT" and year <= 2023 and mois > total_mois - 2:
                            continue  # leave empty

                        for jour in range(1, 29):  # 28 days/month simplified
                            if bucket == "PERDU_DE_VUE" and mois >= 3 and random.random() < 0.9:
                                # absent
                                if random.random() < 0.8:
                                    continue  # empty -> will be considered not taken
                                code = ModeObservation.ABSENT
                            else:
                                if random.random() > adherence:
                                    # some absences
                                    if random.random() < 0.5:
                                        code = ModeObservation.ABSENT
                                    else:
                                        continue
                                else:
                                    # choose X / - / J
                                    r2 = random.random()
                                    if r2 < 0.55:
                                        code = ModeObservation.PRIS_SOUS_SUPERVISION
                                    elif r2 < 0.85:
                                        code = ModeObservation.AUTO_ADMINISTRE
                                    else:
                                        code = ModeObservation.RELAIS_COMMUNAUTAIRE
                            # create
                            ObservanceJournaliere.objects.create(traitement=traitement, mois=mois, jour=jour, statut=code)

                    # For PERDU_DE_VUE active flag: set if EN_TRAITEMENT and we want to flag
                    if bucket == "EN_TRAITEMENT" and random.random() < 0.07:  # ~20/300
                        # set perdu_de_vue date to last prise or debut + 60 days
                        last_date = base_date + timedelta(days=60)
                        traitement.perdu_de_vue = last_date
                        traitement.save(update_fields=["perdu_de_vue"])
                    elif bucket == "PERDU_DE_VUE":
                        # closed as lost: already handled via issue, but also set perdu_de_vue flag before closure?
                        pass

                    # Visites
                    nb_visites = random.randint(0, 4) if bucket not in ("DECEDE",) else random.randint(0, 2)
                    # ensure at least 1 for GUERI/TERMINE
                    if bucket in ("GUERI", "TERMINE") and nb_visites == 0 and random.random() < 0.7:
                        nb_visites = random.randint(1, 3)
                    for v_idx in range(nb_visites):
                        v_date = base_date + timedelta(days=random.randint(15, total_mois * 30 - 5))
                        # keep within year+duration, but allow crossing year
                        poids_visite = None
                        if random.random() < 0.7 and poids is not None:
                            # evolve weight +-3kg
                            w = float(poids) + random.uniform(-3, 3)
                            w = max(15, min(100, w))
                            poids_visite = Decimal(str(round(w, 1)))
                            # update patient poids to last visite weight occasionally
                            if v_idx == nb_visites - 1 and random.random() < 0.5:
                                Patient.objects.filter(pk=patient.pk).update(poids=poids_visite)
                        VisiteSuivi.objects.create(
                            traitement=traitement,
                            date=v_date,
                            poids=poids_visite,
                            troubles_visuels=random.random() < 0.08,
                            jaunisse=random.random() < 0.06,
                            eruption_cutanee=random.random() < 0.09,
                            vertiges=random.random() < 0.07,
                            autres_effets=random.choice(["", "", "Nausées légères.", "Fatigue."]),
                            observations=random.choice(["", "Bonne évolution.", "Tolérance correcte."]),
                            cree_par=infirmier,
                        )

                    # Modifications traitement (historique)
                    if random.random() < 0.08:  # ~8% have modification
                        tmod = random.choice(list(TypeModificationTraitement.values))
                        motif = random.choice([
                            "Intolérance à la rifampicine, adaptation posologique.",
                            "Rechute bacteriologique, passage en retraitement.",
                            "Effet indésirable hépatique, suspension temporaire.",
                            "Prise de poids significative, ajustement posologie.",
                        ])
                        ancien_schema = traitement.schema
                        nouveau_schema = None
                        ancien_poso = traitement.posologie_jour
                        nouveau_poso = None
                        med_susp = ""
                        if tmod == TypeModificationTraitement.CATEGORIE_II:
                            # switch to retreatment
                            schema_ret = schemas.get("2SRHZE/1RHZE/5RHE")
                            if schema_ret and ancien_schema.code != schema_ret.code:
                                traitement.schema = schema_ret
                                traitement.posologie_jour = calculer_posologie(traitement.poids_actuel)
                                traitement.save(update_fields=["schema", "posologie_jour"])
                                nouveau_schema = schema_ret
                                nouveau_poso = traitement.posologie_jour
                            else:
                                # already retreatment, skip
                                tmod = TypeModificationTraitement.CHANGEMENT_POSOLOGIE
                        if tmod == TypeModificationTraitement.CHANGEMENT_POSOLOGIE:
                            nouveau_poso = (ancien_poso or 3) + random.choice([-1, 1])
                            nouveau_poso = max(1, min(6, nouveau_poso))
                            traitement.posologie_jour = nouveau_poso
                            traitement.save(update_fields=["posologie_jour"])
                        if tmod == TypeModificationTraitement.SUSPENSION_MEDICAMENT:
                            med_susp = random.choice(["EH", "S", "R", "H"])
                        HistoriqueModificationTraitement.objects.create(
                            traitement=traitement,
                            medecin=medecin,
                            type_modification=tmod,
                            motif_medical=motif,
                            ancien_schema=ancien_schema if nouveau_schema else None,
                            nouveau_schema=nouschema if (nouschema := nouveau_schema) else None,
                            ancien_posologie_jour=ancien_poso,
                            nouveau_posologie_jour=nouveau_poso,
                            medicament_suspendu=med_susp,
                            description="Modification tracée dans le seed.",
                        )

                    # Contrôles de suivi C2 / C5 / FIN for GUERI/TERMINE/ECHEC
                    if bucket in ("GUERI", "TERMINE", "ECHEC"):
                        # C2 always
                        c2_dt = base_date + timedelta(days=60 + random.randint(-5, 5))
                        c2_year = c2_dt.year
                        if 2021 <= c2_year <= 2026:
                            codes_c = choose_exam_codes_for_suivi()
                            # ensure bacilloscopie for conversion test
                            if "BACILLOSCOPIE" not in codes_c:
                                codes_c.append("BACILLOSCOPIE")
                            pres_c2 = create_prescription(MotifExamen.SUIVI_CONTROLE, NatureEchantillon.PULMONAIRE, MoisControle.C2, codes_c, c2_dt)
                            # for GUERI/TERMINE -> negative, for ECHEC -> positive
                            is_pos_c2 = (bucket == "ECHEC" and random.random() < 0.7)
                            create_resultat(pres_c2, is_positive=is_pos_c2, base_dt=c2_dt)
                        if bucket in ("GUERI", "TERMINE") or (bucket == "ECHEC" and random.random() < 0.6):
                            # C5
                            c5_dt = base_date + timedelta(days=150 + random.randint(-5, 5))
                            c5_year = c5_dt.year
                            if 2021 <= c5_year <= 2026:
                                codes_c = choose_exam_codes_for_suivi()
                                pres_c5 = create_prescription(MotifExamen.SUIVI_CONTROLE, NatureEchantillon.PULMONAIRE, MoisControle.C5, codes_c, c5_dt)
                                is_pos_c5 = (bucket == "ECHEC")
                                create_resultat(pres_c5, is_positive=is_pos_c5, base_dt=c5_dt)
                        if bucket in ("GUERI", "TERMINE"):
                            # FIN
                            fin_dt = base_date + timedelta(days=total_mois * 30 + random.randint(-7, 7))
                            fin_year = fin_dt.year
                            if 2021 <= fin_year <= 2026:
                                codes_c = ["BACILLOSCOPIE"]
                                pres_fin = create_prescription(MotifExamen.SUIVI_CONTROLE, NatureEchantillon.PULMONAIRE, MoisControle.FIN, codes_c, fin_dt)
                                create_resultat(pres_fin, is_positive=False, base_dt=fin_dt)
                    elif bucket == "EN_TRAITEMENT" and random.random() < 0.25:
                        # 25% have a C2 pending or done
                        c2_dt = base_date + timedelta(days=60 + random.randint(-5, 10))
                        if 2021 <= c2_dt.year <= 2026:
                            codes_c = ["BACILLOSCOPIE"]
                            pres_c2 = create_prescription(MotifExamen.SUIVI_CONTROLE, NatureEchantillon.PULMONAIRE, MoisControle.C2, codes_c, c2_dt)
                            if random.random() < 0.5:
                                create_resultat(pres_c2, is_positive=random.random() < 0.3, base_dt=c2_dt)

                    # Rendez-vous
                    nb_rdv = random.randint(0, 3)
                    if bucket in ("GUERI", "TERMINE", "EN_TRAITEMENT") and random.random() < 0.6:
                        nb_rdv = random.randint(1, 3)
                    for _ in range(nb_rdv):
                        # date after admission
                        rdv_date = (adm_dt.date() + timedelta(days=random.randint(7, total_mois * 30)))
                        # cap at 2026-12-31
                        if rdv_date.year > 2026:
                            rdv_date = date(2026, 12, random.randint(1, 28))
                        heure = time(random.choice([8, 9, 10, 11, 13, 14, 15]), random.choice([0, 15, 30, 45]))
                        # check conflict
                        tries = 0
                        while (rdv_date, heure) in rdv_slots and tries < 5:
                            heure = time(heure.hour, random.choice([0, 15, 30, 45]))
                            if tries > 2:
                                rdv_date = rdv_date + timedelta(days=1)
                            tries += 1
                        if (rdv_date, heure) in rdv_slots:
                            continue
                        rdv_slots.add((rdv_date, heure))
                        rdv_type = random.choice(list(TypeRendezVous.values))
                        rdv_statut = random.choices(
                            [StatutRendezVous.PLANIFIE, StatutRendezVous.EFFECTUE, StatutRendezVous.ANNULE],
                            weights=[0.6, 0.30, 0.10]
                        )[0]
                        # if rdv in future relative to today (2026-08-22), keep PLANIFIE
                        if rdv_date > date(2026, 8, 22) and rdv_statut != StatutRendezVous.PLANIFIE:
                            rdv_statut = StatutRendezVous.PLANIFIE
                        RendezVous.objects.create(
                            patient=patient,
                            date=rdv_date,
                            heure=heure,
                            type=rdv_type,
                            statut=rdv_statut,
                            motif=random.choice(["", "Contrôle mensuel", "Remise médicaments", "Lecture C2"]),
                            cree_par=infirmier,
                        )

                    # Verrou dossier 5%
                    if random.random() < 0.05:
                        try:
                            VerrouDossier.objects.create(
                                patient=patient,
                                utilisateur=random.choice(infirmiers + medecins),
                                expire_le=timezone.now() + timedelta(minutes=VerrouDossier.DUREE_VERROU_MINUTES),
                            )
                        except Exception:
                            pass

                    # Clôture for closed buckets
                    if is_closed_bucket:
                        issue = pick_issue_finale_for_bucket(bucket)
                        # date_issue = base_date + duree traitement + delta
                        if bucket == "DECEDE":
                            date_issue = base_date + timedelta(days=random.randint(20, 60))
                        elif bucket == "TRANSFERE":
                            date_issue = base_date + timedelta(days=random.randint(30, 90))
                        elif bucket == "PERDU_DE_VUE":
                            date_issue = base_date + timedelta(days=random.randint(70, 120))
                        else:
                            date_issue = base_date + timedelta(days=total_mois * 30 + random.randint(-10, 20))
                        # ensure not beyond 2026-12
                        if date_issue.year > 2026:
                            date_issue = date(2026, random.randint(6, 12), random.randint(1, 28))
                        traitement.statut = StatutTraitement.CLOTURE
                        traitement.issue_finale = issue
                        traitement.issue_decision_date = date_issue
                        traitement.cloture_par = medecin
                        traitement.save()
                        # update patient statut accordingly
                        if issue == IssueFinale.GUERI:
                            patient.statut = StatutDossier.GUERI
                        else:
                            patient.statut = StatutDossier.CLOTURE
                        patient.save(update_fields=["statut"])
                    else:
                        # EN_TRAITEMENT stays
                        pass

                created += 1
                if created % 100 == 0:
                    self.stdout.write(f"  ... {created}/{count} patients créés")

        self.stdout.write(self.style.SUCCESS(f"Seed terminé: {created} patients créés (répartis 2021-2025, 10 buckets statuts)."))
        # Summary
        from django.db.models import Count
        self.stdout.write("Répartition finale Patient.statut:")
        for row in Patient.objects.values("statut").annotate(c=Count("id")).order_by("statut"):
            self.stdout.write(f"  {row['statut']}: {row['c']}")
        self.stdout.write("Traitement issues:")
        for row in Traitement.objects.values("issue_finale").annotate(c=Count("id")).order_by("issue_finale"):
            self.stdout.write(f"  {row['issue_finale'] or '(en cours)'}: {row['c']}")
        self.stdout.write(f"Examens: {ExamenPrescription.objects.count()} prescriptions, {ResultatLabo.objects.count()} résultats, {InterpretationResultat.objects.count()} interprétations")
        self.stdout.write(f"Observance: {ObservanceJournaliere.objects.count()} prises, Visites: {VisiteSuivi.objects.count()}, RDV: {RendezVous.objects.count()}")
