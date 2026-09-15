import random
from calendar import monthrange
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.patients.models import (
    EpisodeTB, Patient, Traitement, TypeCasTraitement,
    StatutEpisodeTB, TypePatient, SiteMaladie, IssueFinale,
)
from apps.users.models import CustomUser, UserRole


class Command(BaseCommand):
    help = "Crée des EpisodeTB avec au moins 5 nouveaux cas par mois sur les 12 derniers mois."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=99)
        parser.add_argument("--clear", action="store_true")

    def handle(self, *args, **options):
        random.seed(options["seed"])

        if options["clear"]:
            EpisodeTB.objects.all().delete()
            self.stdout.write("EpisodeTB cleared.")

        medecins = list(CustomUser.objects.filter(role=UserRole.MEDECIN, is_active=True))
        if not medecins:
            self.stderr.write("Aucun médecin trouvé.")
            return

        patients = list(Patient.objects.all().order_by("cree_le"))
        if not patients:
            self.stderr.write("Aucun patient trouvé. Lancez d'abord seed_patients.")
            return

        today = timezone.localdate()
        created = 0
        used_patients = set()

        # ── Phase 1 : 5 nouveaux cas par mois sur 12 derniers mois ──
        for i in range(11, -1, -1):
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            _, last_day = monthrange(y, m)
            for _ in range(5):
                # pick unused patient
                avail = [p for p in patients if p.pk not in used_patients]
                if not avail:
                    break
                p = random.choice(avail)
                used_patients.add(p.pk)

                jour = random.randint(1, last_day)
                date_ouverture = date(y, m, jour)

                statut = random.choices(
                    [StatutEpisodeTB.EN_TRAITEMENT, StatutEpisodeTB.CLOTURE, StatutEpisodeTB.CONFIRME, StatutEpisodeTB.PROVISOIRE],
                    weights=[0.5, 0.3, 0.1, 0.1]
                )[0]

                type_patient = random.choices(
                    [TypePatient.NOUVEAU, TypePatient.RECHUTE],
                    weights=[0.85, 0.15]
                )[0]

                resultat = ""
                date_cloture = None
                if statut == StatutEpisodeTB.CLOTURE:
                    resultat = random.choices(
                        ["GUERI", "ECHEC", "PERDU_DE_VUE", "DECEDE", "TRANSFERE"],
                        weights=[0.55, 0.1, 0.15, 0.1, 0.1]
                    )[0]
                    date_cloture = date_ouverture + timedelta(days=random.randint(90, 240))

                EpisodeTB.objects.create(
                    patient=p,
                    date_ouverture=date_ouverture,
                    statut=statut,
                    type_patient=type_patient,
                    site_maladie=random.choice(list(SiteMaladie)),
                    diagnostic=random.choice(["", "Tuberculose pulmonaire", "Tuberculose extra-pulmonaire"]),
                    resultat_final=resultat,
                    date_cloture=date_cloture,
                    cree_par=random.choice(medecins),
                )
                created += 1

        # ── Phase 2 : remaining patients ──
        for p in patients:
            if p.pk in used_patients:
                continue

            traitement = Traitement.objects.filter(patient=p).first()

            if p.statut in ("PROVISOIRE",):
                statut_ep = StatutEpisodeTB.PROVISOIRE
                resultat = ""
            elif p.statut in ("CONFIRME",):
                statut_ep = StatutEpisodeTB.CONFIRME
                resultat = ""
            elif p.statut in ("EN_TRAITEMENT",):
                statut_ep = StatutEpisodeTB.EN_TRAITEMENT
                resultat = ""
            elif p.statut in ("GUERI", "CLOTURE"):
                statut_ep = StatutEpisodeTB.CLOTURE
                if traitement:
                    mapping = {
                        IssueFinale.GUERI: "GUERI",
                        IssueFinale.TERMINE: "GUERI",
                        IssueFinale.ECHEC: "ECHEC",
                        IssueFinale.DECEDE: "DECEDE",
                        IssueFinale.PERDU_DE_VUE: "PERDU_DE_VUE",
                        IssueFinale.TRANSFERE: "TRANSFERE",
                    }
                    resultat = mapping.get(traitement.issue_finale, "GUERI")
                else:
                    resultat = "GUERI"
            else:
                statut_ep = StatutEpisodeTB.PROVISOIRE
                resultat = ""

            type_patient = TypePatient.RECHUTE if (traitement and traitement.type_cas == TypeCasTraitement.RECHUTE) else TypePatient.NOUVEAU

            date_ouverture = p.cree_le.date() if p.cree_le else date(2025, 1, 1)
            date_cloture = None
            if statut_ep == StatutEpisodeTB.CLOTURE:
                if traitement and traitement.issue_decision_date:
                    date_cloture = traitement.issue_decision_date
                else:
                    date_cloture = date_ouverture + timedelta(days=random.randint(120, 240))

            EpisodeTB.objects.create(
                patient=p,
                date_ouverture=date_ouverture,
                statut=statut_ep,
                type_patient=type_patient,
                site_maladie=random.choice(list(SiteMaladie)),
                diagnostic=random.choice(["", "Tuberculose pulmonaire", "Tuberculose extra-pulmonaire"]),
                resultat_final=resultat,
                date_cloture=date_cloture,
                cree_par=random.choice(medecins),
            )
            used_patients.add(p.pk)
            created += 1

        total = EpisodeTB.objects.count()
        nouveaux = EpisodeTB.objects.filter(type_patient=TypePatient.NOUVEAU).count()
        rechutes = EpisodeTB.objects.filter(type_patient=TypePatient.RECHUTE).count()
        self.stdout.write(self.style.SUCCESS(
            f"EpisodeTB: {created} créés, {total} total ({nouveaux} nouveaux, {rechutes} rechutes)"
        ))
