from datetime import date, timedelta, time

from django.test import TestCase
from django.urls import reverse

from apps.users.models import CustomUser, UserRole

from .models import (
    DecisionDiagnostic,
    ExamenPrescription,
    InterpretationResultat,
    Notification,
    ObservanceJournaliere,
    Patient,
    ResultatLabo,
    RendezVous,
    StatutDossier,
    StatutExamen,
    StatutResultat,
    StatutTraitement,
    Traitement,
    TypeExamen,
    VerrouDossier,
)
from .services import (
    acquerir_verrou,
    admission_est_finalisable,
    calculer_posologie,
    cloturer_traitement,
    cohorte_guerison,
    creer_dossier_provisoire,
    creer_prescription_examen,
    creer_traitement,
    derniere_prise,
    detecter_perdus_de_vue,
    enregistrer_interpretation,
    enregistrer_observance,
    enregistrer_resultats,
    enregistrer_visite,
    finaliser_admission,
    liberer_verrou,
    mettre_a_jour_informations,
    modifier_traitement,
    programmer_rendez_vous,
    statut_rendez_vous,
    trouver_controle_en_attente,
)
from .views import NotificationSseView


class PatientModelTests(TestCase):
    def setUp(self):
        self.medecin = CustomUser.objects.create_user(
            username='dr.test@hgr-makala.cd',
            password='password123',
            email='dr.test@hgr-makala.cd',
            first_name='Paul',
            last_name='Kalombo',
            role=UserRole.MEDECIN,
            is_active=True,
        )

    def _creer(self, **kwargs):
        donnees = {
            'nom': 'Mbuyi',
            'post_nom': 'Kanyinda',
            'prenom': 'Claire',
            'sexe': 'F',
            'date_naissance': date(1990, 5, 12),
            'district': 'Mont-Ngafula',
            'secteur': 'Secteur 1',
            'cellule': 'Cellule A',
            'village': 'Village B',
        }
        donnees.update(kwargs)
        return creer_dossier_provisoire(medecin=self.medecin, donnees=donnees)

    def test_generer_ndp_incremental(self):
        p1 = self._creer()
        p2 = self._creer()
        annee = date.today().year
        self.assertEqual(p1.ndp, f'NDP-{annee}-0001')
        self.assertEqual(p2.ndp, f'NDP-{annee}-0002')

    def test_age_calcule(self):
        patient = self._creer(date_naissance=date(1990, 5, 12))
        aujourd = date.today()
        attendu = aujourd.year - 1990 - ((aujourd.month, aujourd.day) < (5, 12))
        self.assertEqual(patient.age, attendu)
        enfant = self._creer(nom='Enfant', prenom='Petit', date_naissance=date.today())
        self.assertEqual(enfant.age, 0)

    def test_trouver_doublon(self):
        self._creer()
        doublon = Patient.trouver_doublon(
            nom='mbuyi', prenom='claire', date_naissance=date(1990, 5, 12)
        )
        self.assertEqual(doublon.full_name, 'Claire Kanyinda Mbuyi')

    def test_dossier_provisoire_statut_par_defaut(self):
        patient = self._creer()
        self.assertEqual(patient.statut, StatutDossier.PROVISOIRE)
        self.assertEqual(patient.cree_par, self.medecin)
        self.assertTrue(patient.ndp.startswith('NDP-'))


class PatientViewsTests(TestCase):
    def setUp(self):
        self.medecin = CustomUser.objects.create_user(
            username='dr.test@hgr-makala.cd',
            password='password123',
            email='dr.test@hgr-makala.cd',
            first_name='Paul',
            last_name='Kalombo',
            role=UserRole.MEDECIN,
            is_active=True,
        )
        self.infermier = CustomUser.objects.create_user(
            username='inf.test@hgr-makala.cd',
            password='password123',
            email='inf.test@hgr-makala.cd',
            first_name='Claire',
            last_name='Bofassa',
            role=UserRole.INFIRMIER,
            is_active=True,
        )
        self.laborantin = CustomUser.objects.create_user(
            username='lab.test@hgr-makala.cd',
            password='password123',
            email='lab.test@hgr-makala.cd',
            first_name='Jean',
            last_name='Bofasa',
            role=UserRole.LABORANTIN,
            is_active=True,
        )

    def _donnees_valides(self, **kwargs):
        donnees = {
            'nom': 'Mbuyi',
            'post_nom': 'Kanyinda',
            'prenom': 'Claire',
            'sexe': 'F',
            'date_naissance': '1990-05-12',
            'district': 'Mont-Ngafula',
            'secteur': 'Secteur 1',
            'cellule': 'Cellule A',
            'village': 'Village B',
            'telephone': '+243 81 000 0000',
            'poids': '55.5',
        }
        donnees.update(kwargs)
        return donnees

    def test_patient_list_requires_login(self):
        response = self.client.get(reverse('patient_list'))
        self.assertEqual(response.status_code, 302)

    def test_patient_list_allows_infirmier(self):
        """US3.3 : l'infirmier peut rechercher les dossiers patients."""
        self.client.login(username='inf.test@hgr-makala.cd', password='password123')
        response = self.client.get(reverse('patient_list'))
        self.assertEqual(response.status_code, 200)

    def test_patient_list_denies_laborantin(self):
        self.client.login(username='lab.test@hgr-makala.cd', password='password123')
        response = self.client.get(reverse('patient_list'))
        self.assertRedirects(response, reverse('notification'))

    def test_patient_list_medecin(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        creer_dossier_provisoire(
            medecin=self.medecin,
            donnees={
                'nom': 'Mbuyi', 'post_nom': 'Kanyinda', 'prenom': 'Claire',
                'sexe': 'F', 'date_naissance': date(1990, 5, 12),
            },
        )
        response = self.client.get(reverse('patient_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Claire Kanyinda Mbuyi')

    def test_patient_create_form_renders_date_and_placeholders(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        response = self.client.get(reverse('patient_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'type="date"')
        self.assertContains(response, 'placeholder="ex. Kalombo"')
        self.assertContains(response, 'placeholder="ex. Paul"')
        self.assertContains(response, 'placeholder="+243 8X XXX XXXX"')

    def test_patient_create_success(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        response = self.client.post(
            reverse('patient_create'), self._donnees_valides()
        )
        patient = Patient.objects.get()
        self.assertEqual(patient.full_name, 'Claire Kanyinda Mbuyi')
        self.assertEqual(patient.ndp, f'NDP-{date.today().year}-0001')
        self.assertEqual(patient.statut, StatutDossier.PROVISOIRE)
        self.assertRedirects(response, reverse('patient_detail', kwargs={'pk': patient.pk}))

    def test_patient_create_duplicate_flagged(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        self.client.post(reverse('patient_create'), self._donnees_valides())
        response = self.client.post(reverse('patient_create'), self._donnees_valides())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dossier provisoire')  # page rendue avec avis
        self.assertEqual(Patient.objects.count(), 1)

    def test_patient_create_future_birthdate_invalid(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        response = self.client.post(
            reverse('patient_create'), self._donnees_valides(date_naissance='2999-01-01')
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ne peut pas être dans le futur")
        self.assertEqual(Patient.objects.count(), 0)

    def test_patient_create_action_prescrire_redirects_to_prescription(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        donnees = self._donnees_valides()
        donnees['action'] = 'prescrire'
        response = self.client.post(reverse('patient_create'), donnees)
        patient = Patient.objects.get()
        self.assertRedirects(
            response, reverse('prescription_create', kwargs={'pk': patient.pk})
        )

    def test_patient_detail_medecin(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = creer_dossier_provisoire(
            medecin=self.medecin,
            donnees={
                'nom': 'Mbuyi', 'post_nom': 'Kanyinda', 'prenom': 'Claire',
                'sexe': 'F', 'date_naissance': date(1990, 5, 12),
                'district': 'Mont-Ngafula',
                'signe_toux_persistante': True,
                'comorb_vih': True,
            },
        )
        response = self.client.get(
            reverse('patient_detail', kwargs={'pk': patient.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, patient.ndp)
        self.assertContains(response, 'Toux persistante')
        self.assertContains(response, 'VIH/SIDA')

    def test_patient_detail_allows_infirmier(self):
        """US3.4 : l'infirmier consulte le dossier ; le rapport médical est masqué."""
        self.client.login(username='inf.test@hgr-makala.cd', password='password123')
        patient = creer_dossier_provisoire(
            medecin=self.medecin,
            donnees={
                'nom': 'Mbuyi', 'prenom': 'Claire', 'sexe': 'F',
                'date_naissance': date(1990, 5, 12),
            },
        )
        response = self.client.get(reverse('patient_detail', kwargs={'pk': patient.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, patient.full_name)
        self.assertContains(response, 'Modifier les informations')
        # Le rapport médical / la prescription est réservé au médecin : absent pour l'infirmier.
        self.assertNotContains(response, 'Prescrire un examen')
        self.assertNotContains(response, 'Interprétation du diagnostic')

    def test_patient_detail_denies_laborantin(self):
        self.client.login(username='lab.test@hgr-makala.cd', password='password123')
        patient = creer_dossier_provisoire(
            medecin=self.medecin,
            donnees={
                'nom': 'Mbuyi', 'prenom': 'Claire', 'sexe': 'F',
                'date_naissance': date(1990, 5, 12),
            },
        )
        response = self.client.get(reverse('patient_detail', kwargs={'pk': patient.pk}))
        self.assertRedirects(response, reverse('notification'))


class PrescriptionExamenTests(TestCase):
    def setUp(self):
        self.medecin = CustomUser.objects.create_user(
            username='dr.test@hgr-makala.cd',
            password='password123',
            email='dr.test@hgr-makala.cd',
            first_name='Paul',
            last_name='Kalombo',
            role=UserRole.MEDECIN,
            is_active=True,
        )
        self.infermier = CustomUser.objects.create_user(
            username='inf.test@hgr-makala.cd',
            password='password123',
            email='inf.test@hgr-makala.cd',
            first_name='Claire',
            last_name='Bofassa',
            role=UserRole.INFIRMIER,
            is_active=True,
        )

    def _patient(self, **kwargs):
        donnees = {
            'nom': 'Mbuyi',
            'post_nom': 'Kanyinda',
            'prenom': 'Claire',
            'sexe': 'F',
            'date_naissance': date(1990, 5, 12),
            'signe_toux_persistante': True,
        }
        donnees.update(kwargs)
        return creer_dossier_provisoire(medecin=self.medecin, donnees=donnees)

    def _donnees_prescription(self, **kwargs):
        bacillo = TypeExamen.objects.get(code='BACILLOSCOPIE')
        vih = TypeExamen.objects.get(code='VIH')
        donnees = {
            'nature_echantillon': 'P',
            'organe': '',
            'motif': 'DIAGNOSTIC',
            'mois_controle': '',
            'examens': [bacillo.pk, vih.pk],
            'date_prelevement': date.today().isoformat(),
            'statut_vih': '',
            'observations': 'Suspect TB pulmonaire.',
        }
        donnees.update(kwargs)
        return donnees

    def test_prescription_requires_login(self):
        patient = self._patient()
        response = self.client.get(reverse('prescription_create', kwargs={'pk': patient.pk}))
        self.assertEqual(response.status_code, 302)

    def test_prescription_requires_medecin(self):
        self.client.login(username='inf.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        response = self.client.get(reverse('prescription_create', kwargs={'pk': patient.pk}))
        self.assertRedirects(response, reverse('notification'))

    def test_prescription_form_prefill_pulmonaire(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient(signe_toux_persistante=True)
        response = self.client.get(reverse('prescription_create', kwargs={'pk': patient.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, patient.ndp)
        self.assertContains(response, 'value="P" selected')
        self.assertContains(response, 'Test VIH')
        self.assertContains(response, 'type="date"')

    def test_prescription_form_prefill_extra_pulmonaire_sans_symptomes(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient(signe_toux_persistante=False)
        response = self.client.get(reverse('prescription_create', kwargs={'pk': patient.pk}))
        self.assertContains(response, 'value="EP" selected')

    def test_prescription_creation_success(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        response = self.client.post(
            reverse('prescription_create', kwargs={'pk': patient.pk}),
            self._donnees_prescription(),
        )
        self.assertRedirects(response, reverse('patient_detail', kwargs={'pk': patient.pk}))
        demandes = ExamenPrescription.objects.filter(patient=patient)
        self.assertEqual(demandes.count(), 1)
        demande = demandes.get()
        self.assertEqual(demande.numero_demande, f'DM-{date.today().year}-0001')
        self.assertEqual(demande.statut, StatutExamen.EN_ATTENTE)
        self.assertEqual(demande.medecin, self.medecin)
        self.assertEqual(demande.nature_echantillon, 'P')
        self.assertEqual(demande.motif, 'DIAGNOSTIC')
        self.assertTrue(demande.date_prescription)
        self.assertEqual(demande.examens.count(), 2)

    def test_prescription_dst_requires_culture(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        dst = TypeExamen.objects.get(code='DST')
        response = self.client.post(
            reverse('prescription_create', kwargs={'pk': patient.pk}),
            self._donnees_prescription(examens=[dst.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test de sensibilité (DST)')
        self.assertContains(response, 'la culture est également demandée')
        self.assertEqual(ExamenPrescription.objects.count(), 0)

    def test_prescription_extra_pulmonaire_requires_organe(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        response = self.client.post(
            reverse('prescription_create', kwargs={'pk': patient.pk}),
            self._donnees_prescription(nature_echantillon='EP', organe=''),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Précisez l’organe')
        self.assertEqual(ExamenPrescription.objects.count(), 0)

    def test_prescription_suivi_requires_mois_controle(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        response = self.client.post(
            reverse('prescription_create', kwargs={'pk': patient.pk}),
            self._donnees_prescription(motif='SUIVI', mois_controle=''),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'mois de contrôle')
        self.assertEqual(ExamenPrescription.objects.count(), 0)

    def test_prescription_future_or_today_date_accepted(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        gene = TypeExamen.objects.get(code='GENEXPERT')
        vih = TypeExamen.objects.get(code='VIH')
        # Aujourd'hui, avec bacilloscopie + VIH
        response = self.client.post(
            reverse('prescription_create', kwargs={'pk': patient.pk}),
            self._donnees_prescription(
                date_prelevement=date.today().isoformat(),
                examens=[
                    TypeExamen.objects.get(code='BACILLOSCOPIE').pk,
                    vih.pk,
                ],
            ),
        )
        self.assertRedirects(response, reverse('patient_detail', kwargs={'pk': patient.pk}))
        # Date future, avec un autre type d'examen (évalue la contrainte sur la date)
        response = self.client.post(
            reverse('prescription_create', kwargs={'pk': patient.pk}),
            self._donnees_prescription(
                date_prelevement=(date.today() + timedelta(days=3)).isoformat(),
                examens=[gene.pk, vih.pk],
            ),
        )
        self.assertRedirects(response, reverse('patient_detail', kwargs={'pk': patient.pk}))
        self.assertEqual(ExamenPrescription.objects.count(), 2)

    def test_prescription_past_date_rejected(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        response = self.client.post(
            reverse('prescription_create', kwargs={'pk': patient.pk}),
            self._donnees_prescription(
                date_prelevement=(date.today() - timedelta(days=1)).isoformat()
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ne peut pas être dans le passé')
        self.assertEqual(ExamenPrescription.objects.count(), 0)

    def test_prescription_duplicate_warns_and_does_not_create(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        bacillo = TypeExamen.objects.get(code='BACILLOSCOPIE')
        vih = TypeExamen.objects.get(code='VIH')
        creer_prescription_examen(
            medecin=self.medecin,
            patient=patient,
            donnees={
                'nature_echantillon': 'P',
                'organe': '',
                'motif': 'DIAGNOSTIC',
                'mois_controle': '',
                'date_prelevement': date.today(),
                'statut_vih': '',
                'observations': '',
            },
            types_examens=[bacillo, vih],
        )
        response = self.client.post(
            reverse('prescription_create', kwargs={'pk': patient.pk}),
            self._donnees_prescription(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Demande(s) identique(s)')
        self.assertContains(response, f'DM-{date.today().year}-0001')
        self.assertEqual(ExamenPrescription.objects.count(), 1)

    def test_patient_detail_shows_prescriptions(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        bacillo = TypeExamen.objects.get(code='BACILLOSCOPIE')
        creer_prescription_examen(
            medecin=self.medecin,
            patient=patient,
            donnees={
                'nature_echantillon': 'P',
                'organe': '',
                'motif': 'DIAGNOSTIC',
                'mois_controle': '',
                'date_prelevement': date.today(),
                'statut_vih': '',
                'observations': '',
            },
            types_examens=[bacillo],
        )
        response = self.client.get(reverse('patient_detail', kwargs={'pk': patient.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Examens prescrits')
        self.assertContains(response, 'Bacilloscopie des crachats')
        self.assertContains(response, f'DM-{date.today().year}-0001')


class LaboratoireModuleTests(TestCase):
    def setUp(self):
        self.medecin = CustomUser.objects.create_user(
            username='dr.test@hgr-makala.cd',
            password='password123',
            email='dr.test@hgr-makala.cd',
            first_name='Paul',
            last_name='Kalombo',
            role=UserRole.MEDECIN,
            is_active=True,
        )
        self.laborantin = CustomUser.objects.create_user(
            username='lab.test@hgr-makala.cd',
            password='password123',
            email='lab.test@hgr-makala.cd',
            first_name='Jean',
            last_name='Bofasa',
            role=UserRole.LABORANTIN,
            is_active=True,
        )

    def _patient(self, **kwargs):
        donnees = {
            'nom': 'Mbuyi',
            'post_nom': 'Kanyinda',
            'prenom': 'Claire',
            'sexe': 'F',
            'date_naissance': date(1990, 5, 12),
            'signe_toux_persistante': True,
        }
        donnees.update(kwargs)
        return creer_dossier_provisoire(medecin=self.medecin, donnees=donnees)

    def _prescription(self, patient, codes=('BACILLOSCOPIE', 'VIH')):
        return creer_prescription_examen(
            medecin=self.medecin,
            patient=patient,
            donnees={
                'nature_echantillon': 'P',
                'organe': '',
                'motif': 'DIAGNOSTIC',
                'mois_controle': '',
                'date_prelevement': date.today(),
                'statut_vih': '',
                'observations': '',
            },
            types_examens=list(TypeExamen.objects.filter(code__in=codes)),
        )

    def _donnees_resultats(self, **kwargs):
        donnees = {
            'date_reception': date.today().isoformat(),
            'apparence': 'MUCOPURULENT',
            'echantillon_1': '+',
            'echantillon_2': 'NEG',
            'technique_coloration': 'ZN',
            'resultat_vih': 'NEGATIF',
            'commentaires': '',
        }
        donnees.update(kwargs)
        return donnees

    def test_examen_list_requires_login(self):
        response = self.client.get(reverse('examen_list'))
        self.assertEqual(response.status_code, 302)

    def test_examen_list_requires_laborantin_role(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        response = self.client.get(reverse('examen_list'))
        self.assertRedirects(response, reverse('notification'))

    def test_medecin_cannot_access_result_saisie(self):
        patient = self._patient()
        presc = self._prescription(patient)
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        response = self.client.get(
            reverse('resultat_saisie', kwargs={'pk': presc.pk})
        )
        self.assertRedirects(response, reverse('notification'))

    def test_laborantin_see_list_sections(self):
        self.client.login(username='lab.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        presc = self._prescription(patient)
        response = self.client.get(reverse('examen_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Examens de laboratoire')
        self.assertContains(response, presc.numero_demande)
        self.assertContains(response, 'Claire Kanyinda Mbuyi')
        self.assertContains(response, 'En attente au laboratoire')

    def test_saisie_form_champs_dynamiques(self):
        self.client.login(username='lab.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        presc = self._prescription(
            patient, codes=('BACILLOSCOPIE', 'VIH')
        )
        response = self.client.get(
            reverse('resultat_saisie', kwargs={'pk': presc.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id_echantillon_1')
        self.assertContains(response, 'id_resultat_vih')
        # Pas de GeneXpert prescrit : champ absent
        self.assertNotContains(response, 'id_resultat_genexpert')

    def test_resultats_brouillon_conserve_statut(self):
        self.client.login(username='lab.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        presc = self._prescription(patient)
        response = self.client.post(
            reverse('resultat_saisie', kwargs={'pk': presc.pk}),
            {**self._donnees_resultats(), 'action': 'brouillon'},
        )
        self.assertRedirects(
            response, reverse('examen_detail', kwargs={'pk': presc.pk})
        )
        presc.refresh_from_db()
        self.assertEqual(presc.statut, StatutExamen.EN_ATTENTE)
        res = ResultatLabo.objects.get(prescription=presc)
        self.assertEqual(res.statut, StatutResultat.BROUILLON)
        self.assertEqual(res.laborantin, self.laborantin)
        self.assertFalse(Notification.objects.filter(
            destinataire=self.medecin
        ).exists())

    def test_validation_resultats_notifie_le_medecin(self):
        self.client.login(username='lab.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        presc = self._prescription(patient)
        response = self.client.post(
            reverse('resultat_saisie', kwargs={'pk': presc.pk}),
            {**self._donnees_resultats(), 'action': 'valider'},
        )
        self.assertRedirects(
            response, reverse('examen_detail', kwargs={'pk': presc.pk})
        )
        presc.refresh_from_db()
        self.assertEqual(presc.statut, StatutExamen.RESULTATS_DISPONIBLES)
        res = ResultatLabo.objects.get(prescription=presc)
        self.assertEqual(res.statut, StatutResultat.VALIDE)
        self.assertEqual(res.laborantin, self.laborantin)
        self.assertEqual(res.echantillon_1, '+')
        self.assertIsNotNone(res.date_lecture)
        notif = Notification.objects.get(destinataire=self.medecin)
        self.assertIn(presc.numero_demande, notif.message)

    def test_revalidation_conserve_traçabilite(self):
        self.client.login(username='lab.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        presc = self._prescription(patient)
        url = reverse('resultat_saisie', kwargs={'pk': presc.pk})
        self.client.post(url, {**self._donnees_resultats(), 'action': 'valider'})
        self.client.post(url, {**self._donnees_resultats(), 'action': 'valider'})
        self.assertEqual(
            ResultatLabo.objects.filter(prescription=presc).count(), 2
        )
        self.assertEqual(
            Notification.objects.filter(destinataire=self.medecin).count(), 2
        )

    def test_validation_rend_le_resultat_visible_au_medecin(self):
        self.client.login(username='lab.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        presc = self._prescription(patient)
        self.client.post(
            reverse('resultat_saisie', kwargs={'pk': presc.pk}),
            {**self._donnees_resultats(), 'action': 'valider'},
        )
        self.client.logout()
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        response = self.client.get(reverse('patient_detail', kwargs={'pk': patient.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, presc.numero_demande)
        self.assertContains(response, 'Résultats disponibles')

    def test_dashboard_medecin_affiche_notification_non_lue(self):
        self.client.login(username='lab.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        presc = self._prescription(patient)
        self.client.post(
            reverse('resultat_saisie', kwargs={'pk': presc.pk}),
            {**self._donnees_resultats(), 'action': 'valider'},
        )
        self.client.logout()
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        response = self.client.get(reverse('notification'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Notifications')
        self.assertContains(response, presc.numero_demande)
        self.assertContains(response, 'Non lu')

    def test_marquer_notifications_lues(self):
        self.client.login(username='lab.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        presc = self._prescription(patient)
        self.client.post(
            reverse('resultat_saisie', kwargs={'pk': presc.pk}),
            {**self._donnees_resultats(), 'action': 'valider'},
        )
        self.client.logout()
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        self.client.post(reverse('notifications_lues'))
        self.assertFalse(
            Notification.objects.filter(
                destinataire=self.medecin, lu=False
            ).exists()
        )

    def test_donnees_sans_echantillon_de_gene_requis(self):
        self.client.login(username='lab.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        presc = self._prescription(patient, codes=('VIH',))
        response = self.client.post(
            reverse('resultat_saisie', kwargs={'pk': presc.pk}),
            {
                'resultat_vih': 'POSITIF',
                'commentaires': 'Test rapide positif.',
                'action': 'valider',
            },
        )
        self.assertRedirects(
            response, reverse('examen_detail', kwargs={'pk': presc.pk})
        )
        presc.refresh_from_db()
        self.assertEqual(presc.statut, StatutExamen.RESULTATS_DISPONIBLES)
        res = ResultatLabo.objects.get(prescription=presc)
        self.assertEqual(res.resultat_vih, 'POSITIF')
        self.assertTrue(res.resultats_positifs)

    def test_prescription_notifie_les_laborantins(self):
        patient = self._patient()
        presc = self._prescription(patient)
        notifs = Notification.objects.filter(destinataire=self.laborantin)
        self.assertEqual(notifs.count(), 1)
        self.assertIn(presc.numero_demande, notifs.get().message)

    def _valider_resultats(self, presc):
        enregistrer_resultats(
            laborantin=self.laborantin,
            prescription=presc,
            donnees={
                'date_reception': date.today(),
                'apparence': 'MUCOPURULENT',
                'echantillon_1': '+',
                'echantillon_2': 'NEG',
                'technique_coloration': 'ZN',
                'resultat_vih': 'NEGATIF',
                'commentaires': '',
            },
            valider=True,
        )

    # ---- US2.5 / UC5 : Consulter les résultats d'un examen ----

    def test_consultation_resultat_requires_login(self):
        patient = self._patient()
        presc = self._prescription(patient)
        url = reverse(
            'consultation_resultat',
            kwargs={'pk': patient.pk, 'prescription_pk': presc.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_consultation_resultat_requires_medecin(self):
        patient = self._patient()
        presc = self._prescription(patient)
        self._valider_resultats(presc)
        self.client.logout()
        self.client.login(username='lab.test@hgr-makala.cd', password='password123')
        url = reverse(
            'consultation_resultat',
            kwargs={'pk': patient.pk, 'prescription_pk': presc.pk},
        )
        response = self.client.get(url)
        self.assertRedirects(response, reverse('notification'))

    def test_medecin_consulte_les_resultats_disponibles(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        presc = self._prescription(patient)
        self._valider_resultats(presc)
        url = reverse(
            'consultation_resultat',
            kwargs={'pk': patient.pk, 'prescription_pk': presc.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, presc.numero_demande)
        self.assertContains(response, 'Résultats du laboratoire')
        self.assertContains(response, 'Interpréter les résultats')
        self.assertContains(response, '+')
        self.assertContains(response, 'Mucopurulent')

    def test_medecin_ne_peut_pas_voir_resultats_en_attente(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        presc = self._prescription(patient)
        url = reverse(
            'consultation_resultat',
            kwargs={'pk': patient.pk, 'prescription_pk': presc.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Résultats en attente')

    def test_consultation_lien_depuis_le_dossier(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        presc = self._prescription(patient)
        self._valider_resultats(presc)
        response = self.client.get(reverse('patient_detail', kwargs={'pk': patient.pk}))
        self.assertContains(response, 'Consulter les résultats')
        self.assertContains(response, presc.numero_demande)

    # ---- US2.6 / UC6 : Interpréter les résultats ----

    def test_interpretation_requires_login(self):
        patient = self._patient()
        presc = self._prescription(patient)
        self._valider_resultats(presc)
        url = reverse(
            'interpretation_resultat',
            kwargs={'pk': patient.pk, 'prescription_pk': presc.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_interpretation_requires_medecin(self):
        patient = self._patient()
        presc = self._prescription(patient)
        self._valider_resultats(presc)
        self.client.login(username='lab.test@hgr-makala.cd', password='password123')
        url = reverse(
            'interpretation_resultat',
            kwargs={'pk': patient.pk, 'prescription_pk': presc.pk},
        )
        response = self.client.get(url)
        self.assertRedirects(response, reverse('notification'))

    def test_interpretation_impossible_sans_resultats(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        presc = self._prescription(patient)
        url = reverse(
            'interpretation_resultat',
            kwargs={'pk': patient.pk, 'prescription_pk': presc.pk},
        )
        response = self.client.get(url)
        self.assertRedirects(
            response,
            reverse(
                'consultation_resultat',
                kwargs={'pk': patient.pk, 'prescription_pk': presc.pk},
            ),
        )
        self.assertFalse(InterpretationResultat.objects.exists())

    def test_interpretation_confirme_le_dossier(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        presc = self._prescription(patient)
        self._valider_resultats(presc)
        url = reverse(
            'interpretation_resultat',
            kwargs={'pk': patient.pk, 'prescription_pk': presc.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Le formulaire reprend les résultats
        self.assertContains(response, 'Résultats analysés')
        self.assertContains(response, 'Tuberculose confirmée')

        response = self.client.post(
            url,
            {
                'interpretation': 'Bacilloscopie positive, tableau clinique évocateur.',
                'observations': 'Toux ≥ 2 semaines, perte de poids.',
                'decision': DecisionDiagnostic.CONFIRMEE,
            },
        )
        self.assertRedirects(
            response,
            reverse(
                'consultation_resultat',
                kwargs={'pk': patient.pk, 'prescription_pk': presc.pk},
            ),
        )
        patient.refresh_from_db()
        self.assertEqual(patient.statut, StatutDossier.CONFIRME)
        interpretation = InterpretationResultat.objects.get(prescription=presc)
        self.assertEqual(interpretation.medecin, self.medecin)
        self.assertEqual(interpretation.decision, DecisionDiagnostic.CONFIRMEE)

    def test_interpretation_infirme_le_dossier(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        presc = self._prescription(patient)
        self._valider_resultats(presc)
        url = reverse(
            'interpretation_resultat',
            kwargs={'pk': patient.pk, 'prescription_pk': presc.pk},
        )
        self.client.post(
            url,
            {
                'interpretation': 'Aucun élément en faveur de la tuberculose.',
                'observations': '',
                'decision': DecisionDiagnostic.INFIRMEE,
            },
        )
        patient.refresh_from_db()
        self.assertEqual(patient.statut, StatutDossier.NON_CONFIRME)

    def test_interpretation_erreur_champ_obligatoire(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        presc = self._prescription(patient)
        self._valider_resultats(presc)
        url = reverse(
            'interpretation_resultat',
            kwargs={'pk': patient.pk, 'prescription_pk': presc.pk},
        )
        response = self.client.post(
            url,
            {'interpretation': '', 'observations': '', 'decision': ''},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rédigez votre interprétation")
        self.assertContains(response, 'Choisissez l’issue du diagnostic')
        self.assertEqual(InterpretationResultat.objects.count(), 0)

    def test_interpretation_unique_par_prescription(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        patient = self._patient()
        presc = self._prescription(patient)
        self._valider_resultats(presc)
        url = reverse(
            'interpretation_resultat',
            kwargs={'pk': patient.pk, 'prescription_pk': presc.pk},
        )
        self.client.post(
            url,
            {'interpretation': 'Décision initiale.', 'observations': '', 'decision': 'INFIRMEE'},
        )
        self.client.post(
            url,
            {'interpretation': 'Décision révisée.', 'observations': 'Nouveaux éléments.', 'decision': 'CONFIRMEE'},
        )
        self.assertEqual(InterpretationResultat.objects.filter(prescription=presc).count(), 1)
        patient.refresh_from_db()
        self.assertEqual(patient.statut, StatutDossier.CONFIRME)

    def test_interpretation_notifie_les_infirmiers(self):
        infirmier = CustomUser.objects.create_user(
            username='inf2.test@hgr-makala.cd',
            password='password123',
            email='inf2.test@hgr-makala.cd',
            first_name='Sara',
            last_name='Bofassa',
            role=UserRole.INFIRMIER,
            is_active=True,
        )
        patient = self._patient()
        presc = self._prescription(patient)
        self._valider_resultats(presc)
        enregistrer_interpretation(
            medecin=self.medecin,
            prescription=presc,
            donnees={
                'interpretation': 'Confirmée.',
                'observations': '',
                'decision': DecisionDiagnostic.CONFIRMEE,
            },
        )
        notif = Notification.objects.get(
            destinataire=infirmier, message__icontains=patient.ndp
        )
        self.assertIn('confirmé', notif.message)


class NotificationSseTests(TestCase):
    def setUp(self):
        self.medecin = CustomUser.objects.create_user(
            username='dr.test@hgr-makala.cd',
            password='password123',
            email='dr.test@hgr-makala.cd',
            first_name='Paul',
            last_name='Kalombo',
            role=UserRole.MEDECIN,
            is_active=True,
        )
        self.laborantin = CustomUser.objects.create_user(
            username='lab.test@hgr-makala.cd',
            password='password123',
            email='lab.test@hgr-makala.cd',
            first_name='Jean',
            last_name='Bofasa',
            role=UserRole.LABORANTIN,
            is_active=True,
        )

    def _patient(self, **kwargs):
        donnees = {
            'nom': 'Mbuyi',
            'post_nom': 'Kanyinda',
            'prenom': 'Claire',
            'sexe': 'F',
            'date_naissance': date(1990, 5, 12),
        }
        donnees.update(kwargs)
        return creer_dossier_provisoire(medecin=self.medecin, donnees=donnees)

    def test_sse_requires_login(self):
        response = self.client.get(reverse('notifications_sse'))
        self.assertEqual(response.status_code, 302)

    def test_sse_pushes_resultat_event_to_medecin(self):
        patient = self._patient()
        presc = creer_prescription_examen(
            medecin=self.medecin,
            patient=patient,
            donnees={
                'nature_echantillon': 'P',
                'organe': '',
                'motif': 'DIAGNOSTIC',
                'mois_controle': '',
                'date_prelevement': date.today(),
                'statut_vih': '',
                'observations': '',
            },
            types_examens=[TypeExamen.objects.get(code='VIH')],
        )
        view = NotificationSseView()
        stream = view._event_stream(self.medecin)
        # Aucune notification au départ : keepalive
        first = next(stream)
        self.assertIn('keepalive', first)
        # Le laborantin valide un résultat : événement poussé sans rechargement
        enregistrer_resultats(
            laborantin=self.laborantin,
            prescription=presc,
            donnees={'resultat_vih': 'NEGATIF', 'commentaires': ''},
            valider=True,
        )
        event = next(stream)
        self.assertIn('event: notification', event)
        self.assertIn(presc.numero_demande, event)
        payload = event.split('data: ', 1)[1].strip()
        self.assertIn('"non_lues": 1', payload)

    def test_sse_pushes_prescription_event_to_laborantin(self):
        patient = self._patient()
        view = NotificationSseView()
        stream = view._event_stream(self.laborantin)
        first = next(stream)
        self.assertIn('keepalive', first)
        presc = creer_prescription_examen(
            medecin=self.medecin,
            patient=patient,
            donnees={
                'nature_echantillon': 'P',
                'organe': '',
                'motif': 'DIAGNOSTIC',
                'mois_controle': '',
                'date_prelevement': date.today(),
                'statut_vih': '',
                'observations': '',
            },
            types_examens=[TypeExamen.objects.get(code='VIH')],
        )
        event = next(stream)
        self.assertIn('event: notification', event)
        self.assertIn(presc.numero_demande, event)


class PatientRechercheEtOngletsTests(TestCase):
    def setUp(self):
        self.medecin = CustomUser.objects.create_user(
            username='dr.test@hgr-makala.cd',
            password='password123',
            email='dr.test@hgr-makala.cd',
            first_name='Paul',
            last_name='Kalombo',
            role=UserRole.MEDECIN,
            is_active=True,
        )
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')

    def test_patient_list_search_filters(self):
        creer_dossier_provisoire(
            medecin=self.medecin,
            donnees={
                'nom': 'Mbuyi', 'post_nom': 'Kanyinda', 'prenom': 'Claire',
                'sexe': 'F', 'date_naissance': date(1990, 5, 12),
            },
        )
        creer_dossier_provisoire(
            medecin=self.medecin,
            donnees={
                'nom': 'Adeleke', 'post_nom': 'Okafor', 'prenom': 'Sara',
                'sexe': 'F', 'date_naissance': date(1985, 1, 1),
            },
        )
        response = self.client.get(reverse('patient_list'), {'q': 'Mbuyi'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Claire Kanyinda Mbuyi')
        self.assertNotContains(response, 'Sara Okafor Adeleke')
        # Filtre par statut
        response = self.client.get(
            reverse('patient_list'), {'statut': StatutDossier.CONFIRME}
        )
        self.assertContains(response, 'Aucun dossier')  # tous provisoires
        self.assertContains(response, 'Provisoires')

    def test_patient_detail_tabs_and_prescription_pagination(self):
        patient = creer_dossier_provisoire(
            medecin=self.medecin,
            donnees={
                'nom': 'Mbuyi', 'post_nom': 'Kanyinda', 'prenom': 'Claire',
                'sexe': 'F', 'date_naissance': date(1990, 5, 12),
                'signe_toux_persistante': True,
                'comorb_vih': True,
            },
        )
        vih = TypeExamen.objects.get(code='VIH')
        for _ in range(9):
            creer_prescription_examen(
                medecin=self.medecin,
                patient=patient,
                donnees={
                    'nature_echantillon': 'P',
                    'organe': '',
                    'motif': 'DIAGNOSTIC',
                    'mois_controle': '',
                    'date_prelevement': date.today(),
                    'statut_vih': '',
                    'observations': '',
                },
                types_examens=[vih],
            )
        response = self.client.get(
            reverse('patient_detail', kwargs={'pk': patient.pk}),
            {'tab': 'examens'},
        )
        self.assertEqual(response.status_code, 200)
        # Onglets présents
        self.assertContains(response, 'Signes et symptômes')
        self.assertContains(response, 'Comorbidités')
        self.assertContains(response, 'Examens prescrits')
        # Pagination : 8 demandes par page -> 2 pages
        self.assertContains(response, 'page=2')
        self.assertContains(response, '– 8 sur 9')
        page2 = self.client.get(
            reverse('patient_detail', kwargs={'pk': patient.pk}),
            {'tab': 'examens', 'page': 2},
        )
        self.assertContains(page2, '9 – 9 sur 9')


class Epic3GestionAdministrativeTests(TestCase):
    """Epic 3 : admission administrative (US3.1/UC1), mise à jour avec
    historique (US3.2/UC2), verrouillage d'édition (UC2/Ex1)."""

    def setUp(self):
        self.medecin = CustomUser.objects.create_user(
            username='dr.test@hgr-makala.cd', password='password123',
            email='dr.test@hgr-makala.cd',
            first_name='Paul', last_name='Kalombo',
            role=UserRole.MEDECIN, is_active=True,
        )
        self.infirmier = CustomUser.objects.create_user(
            username='inf.test@hgr-makala.cd', password='password123',
            email='inf.test@hgr-makala.cd',
            first_name='Claire', last_name='Bofassa',
            role=UserRole.INFIRMIER, is_active=True,
        )
        self.autre_infirmier = CustomUser.objects.create_user(
            username='inf2@hgr-makala.cd', password='password123',
            email='inf2@hgr-makala.cd',
            first_name='Aline', last_name='Kasongo',
            role=UserRole.INFIRMIER, is_active=True,
        )
        self.laborantin = CustomUser.objects.create_user(
            username='lab.test@hgr-makala.cd', password='password123',
            email='lab.test@hgr-makala.cd',
            first_name='Jean', last_name='Bofasa',
            role=UserRole.LABORANTIN, is_active=True,
        )

    def _patient_confirme(self):
        """Crée un patient provisoire puis valide le diagnostic (CONFIRME)."""
        patient = creer_dossier_provisoire(
            medecin=self.medecin,
            donnees={
                'nom': 'Mbuyi', 'post_nom': 'Kanyinda', 'prenom': 'Claire',
                'sexe': 'F', 'date_naissance': date(1990, 5, 12),
                'district': 'Mont-Ngafula',
            },
        )
        presc = creer_prescription_examen(
            medecin=self.medecin, patient=patient,
            donnees={
                'nature_echantillon': 'P', 'organe': '', 'motif': 'DIAGNOSTIC',
                'mois_controle': '', 'date_prelevement': date.today(),
                'statut_vih': '', 'observations': '',
            },
            types_examens=[TypeExamen.objects.get(code='BACILLOSCOPIE')],
        )
        enregistrer_resultats(
            laborantin=self.laborantin, prescription=presc,
            donnees={
                'date_reception': date.today(), 'apparence': 'MUCOPURULENT',
                'echantillon_1': '+', 'echantillon_2': 'NEG',
                'technique_coloration': 'ZN', 'resultat_vih': 'NEGATIF',
                'commentaires': '',
            },
            valider=True,
        )
        enregistrer_interpretation(
            medecin=self.medecin, prescription=presc,
            donnees={
                'interpretation': 'Bacilloscopie positive, TP se confirme.',
                'observations': '',
                'decision': DecisionDiagnostic.CONFIRMEE,
            },
        )
        patient.refresh_from_db()
        self.assertEqual(patient.statut, StatutDossier.CONFIRME)
        return patient

    def _donnees_admission(self, **kwargs):
        donnees = {
            'nom': 'Mbuyi', 'post_nom': 'Kanyinda', 'prenom': 'Claire',
            'sexe': 'F', 'date_naissance': date(1990, 5, 12),
            'district': 'Kinshasa', 'secteur': 'Secteur 2',
            'cellule': 'Cellule C', 'village': 'Village D',
            'telephone': '+243 81 000 0000',
        }
        donnees.update(kwargs)
        return donnees

    # ---- US3.1 / UC1 : Finaliser l'admission administrative ----

    def test_admission_finalisee_avec_champs_obligatoires(self):
        patient = self._patient_confirme()
        patient, doublon = finaliser_admission(
            infirmier=self.infirmier,
            patient=patient,
            donnees=self._donnees_admission(),
        )
        self.assertFalse(doublon)
        patient.refresh_from_db()
        self.assertTrue(patient.admission_finalisee)
        self.assertIsNotNone(patient.date_admission)
        self.assertEqual(patient.admise_par, self.infirmier)
        self.assertEqual(patient.district, 'Kinshasa')

    def test_champs_obligatoires_manquants_refuses(self):
        from django.core.exceptions import ValidationError
        patient = self._patient_confirme()
        donnees = self._donnees_admission()
        del donnees['nom']
        with self.assertRaises(ValidationError):
            finaliser_admission(
                infirmier=self.infirmier,
                patient=patient,
                donnees=donnees,
            )
        patient.refresh_from_db()
        self.assertFalse(patient.admission_finalisee)

    def test_finaliser_admission_deja_finalisee_refusee(self):
        from django.core.exceptions import ValidationError
        patient = self._patient_confirme()
        finaliser_admission(
            infirmier=self.infirmier,
            patient=patient,
            donnees=self._donnees_admission(),
        )
        with self.assertRaises(ValidationError):
            finaliser_admission(
                infirmier=self.infirmier,
                patient=patient,
                donnees=self._donnees_admission(),
            )

    def test_admission_detecte_doublon(self):
        patient = self._patient_confirme()
        doublon = creer_dossier_provisoire(
            medecin=self.medecin,
            donnees={
                'nom': 'Mbuyi', 'post_nom': 'Kanyinda', 'prenom': 'Claire',
                'sexe': 'F', 'date_naissance': date(1990, 5, 12),
                'district': 'Ngaliema',
            },
        )
        resultat, est_doublon = finaliser_admission(
            infirmier=self.infirmier,
            patient=doublon,
            donnees=self._donnees_admission(),
        )
        self.assertTrue(est_doublon)
        self.assertEqual(resultat.pk, patient.pk)

    def test_admission_pas_finalisable_sans_diagnostic_confirme(self):
        patient = creer_dossier_provisoire(
            medecin=self.medecin,
            donnees={
                'nom': 'Mbuyi', 'prenom': 'Claire', 'sexe': 'F',
                'date_naissance': date(1990, 5, 12),
            },
        )
        self.assertFalse(admission_est_finalisable(patient))
        self.assertFalse(patient.admission_finalisee)

    def test_admission_reservee_aux_infirmiers(self):
        patient = self._patient_confirme()
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        response = self.client.get(
            reverse('admission_finaliser', kwargs={'pk': patient.pk})
        )
        self.assertRedirects(response, reverse('notification'))

    def test_vue_admission_refuse_sans_diagnostic_confirme(self):
        patient = creer_dossier_provisoire(
            medecin=self.medecin,
            donnees={
                'nom': 'Mbuyi', 'prenom': 'Claire', 'sexe': 'F',
                'date_naissance': date(1990, 5, 12),
            },
        )
        self.client.login(username='inf.test@hgr-makala.cd', password='password123')
        response = self.client.get(
            reverse('admission_finaliser', kwargs={'pk': patient.pk})
        )
        self.assertRedirects(
            response,
            reverse('patient_detail', kwargs={'pk': patient.pk}),
        )

    def test_vue_admission_finalise_succes(self):
        patient = self._patient_confirme()
        self.client.login(username='inf.test@hgr-makala.cd', password='password123')
        response = self.client.post(
            reverse('admission_finaliser', kwargs={'pk': patient.pk}),
            self._donnees_admission(),
        )
        self.assertRedirects(
            response,
            reverse('patient_detail', kwargs={'pk': patient.pk}),
        )
        patient.refresh_from_db()
        self.assertTrue(patient.admission_finalisee)
        self.assertEqual(patient.telephone, '+243 81 000 0000')

    # ---- US3.2 / UC2 : Mise à jour des informations + historique ----

    def test_mise_a_jour_enregistre_historique(self):
        patient = self._patient_confirme()
        finaliser_admission(
            infirmier=self.infirmier,
            patient=patient,
            donnees=self._donnees_admission(),
        )
        patient.refresh_from_db()
        mettre_a_jour_informations(
            infirmier=self.infirmier,
            patient=patient,
            donnees={
                'district': 'Ngaliema',
                'telephone': '+243 99 000 0000',
            },
        )
        patient.refresh_from_db()
        self.assertEqual(patient.district, 'Ngaliema')
        modification = patient.modifications.filter(champ='district').order_by('-cree_le').first()
        self.assertEqual(modification.ancienne_valeur, 'Kinshasa')
        self.assertEqual(modification.nouvelle_valeur, 'Ngaliema')
        self.assertEqual(modification.auteur, self.infirmier)

    def test_mise_a_jour_sans_changement_pas_dhistorique(self):
        patient = self._patient_confirme()
        finaliser_admission(
            infirmier=self.infirmier,
            patient=patient,
            donnees=self._donnees_admission(),
        )
        patient.refresh_from_db()
        nb_modifs = patient.modifications.count()
        mettre_a_jour_informations(
            infirmier=self.infirmier,
            patient=patient,
            donnees=self._donnees_admission(),
        )
        patient.refresh_from_db()
        self.assertEqual(patient.modifications.count(), nb_modifs)

    def test_vue_mise_a_jour_reservee_aux_infirmiers(self):
        patient = self._patient_confirme()
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        response = self.client.get(
            reverse('patient_admin_update', kwargs={'pk': patient.pk})
        )
        self.assertRedirects(response, reverse('notification'))

    def test_vue_mise_a_jour_succes_et_liberation_verrou(self):
        patient = self._patient_confirme()
        finaliser_admission(
            infirmier=self.infirmier,
            patient=patient,
            donnees=self._donnees_admission(),
        )
        self.client.login(username='inf.test@hgr-makala.cd', password='password123')
        response = self.client.post(
            reverse('patient_admin_update', kwargs={'pk': patient.pk}),
            {
                'nom': 'Mbuyi', 'post_nom': 'Kanyinda', 'prenom': 'Claire',
                'sexe': 'F', 'date_naissance': '1990-05-12',
                'district': 'Ngaliema', 'secteur': '', 'cellule': '',
                'village': '', 'telephone': '+243 99 000 0000',
            },
        )
        self.assertRedirects(
            response,
            reverse('patient_detail', kwargs={'pk': patient.pk}),
        )
        patient.refresh_from_db()
        self.assertEqual(patient.district, 'Ngaliema')
        self.assertFalse(
            VerrouDossier.objects.filter(
                patient=patient, utilisateur=self.infirmier
            ).exists()
        )

    def test_annulation_libère_le_verrou(self):
        patient = self._patient_confirme()
        self.client.login(username='inf.test@hgr-makala.cd', password='password123')
        self.client.get(
            reverse('patient_admin_update', kwargs={'pk': patient.pk})
        )
        response = self.client.post(
            reverse('patient_admin_cancel', kwargs={'pk': patient.pk})
        )
        self.assertRedirects(
            response,
            reverse('patient_detail', kwargs={'pk': patient.pk}),
        )
        self.assertFalse(
            VerrouDossier.objects.filter(
                patient=patient, utilisateur=self.infirmier
            ).exists()
        )

    # ---- UC2 / Variation : Verrou d'édition ----

    def test_verrou_bloque_un_second_utilisateur(self):
        patient = self._patient_confirme()
        verrou = acquerir_verrou(patient, self.infirmier)
        self.assertIsNone(verrou)
        conflit = acquerir_verrou(patient, self.autre_infirmier)
        self.assertIsNotNone(conflit)
        self.assertEqual(conflit.utilisateur, self.infirmier)

    def test_verrou_renouvele_par_le_meme_utilisateur(self):
        patient = self._patient_confirme()
        acquerir_verrou(patient, self.infirmier)
        conflit = acquerir_verrou(patient, self.infirmier)
        self.assertIsNone(conflit)

    def test_verrou_expire_permet_reacquisition(self):
        from django.utils import timezone
        patient = self._patient_confirme()
        acquerir_verrou(patient, self.infirmier)
        patient.verrou.expire_le = timezone.now() - timedelta(minutes=1)
        patient.verrou.save()
        conflit = acquerir_verrou(patient, self.autre_infirmier)
        self.assertIsNone(conflit)

    def test_vue_mise_a_jour_verrouille_pour_second_utilisateur(self):
        patient = self._patient_confirme()
        acquerir_verrou(patient, self.infirmier)
        self.client.login(username='inf2@hgr-makala.cd', password='password123')
        response = self.client.get(
            reverse('patient_admin_update', kwargs={'pk': patient.pk})
        )
        self.assertRedirects(
            response,
            reverse('patient_detail', kwargs={'pk': patient.pk}),
        )

    def test_patient_detail_masque_rapport_medical_pour_infirmier(self):
        patient = self._patient_confirme()
        self.client.login(username='inf.test@hgr-makala.cd', password='password123')
        response = self.client.get(
            reverse('patient_detail', kwargs={'pk': patient.pk})
        )
        self.assertEqual(response.status_code, 200)
        # Le rapport médical / interprétation est réservé au médecin.
        self.assertNotContains(response, 'Interprétation du diagnostic')
        self.assertContains(response, 'Modifier les informations')


class Epic4SuiviTherapeutiqueTests(TestCase):
    """Epic 4 : fiche de traitement (US4.1), bon de contrôle (US4.2),
    carte du malade et registre de cas (US4.3)."""

    def setUp(self):
        self.medecin = CustomUser.objects.create_user(
            username='dr.test@hgr-makala.cd', password='password123',
            email='dr.test@hgr-makala.cd',
            first_name='Paul', last_name='Kalombo',
            role=UserRole.MEDECIN, is_active=True,
        )
        self.infirmier = CustomUser.objects.create_user(
            username='inf.test@hgr-makala.cd', password='password123',
            email='inf.test@hgr-makala.cd',
            first_name='Claire', last_name='Bofassa',
            role=UserRole.INFIRMIER, is_active=True,
        )
        self.laborantin = CustomUser.objects.create_user(
            username='lab.test@hgr-makala.cd', password='password123',
            email='lab.test@hgr-makala.cd',
            first_name='Jean', last_name='Bofasa',
            role=UserRole.LABORANTIN, is_active=True,
        )
        self.patient = creer_dossier_provisoire(
            medecin=self.medecin,
            donnees={
                'nom': 'Mbuyi', 'post_nom': 'Kanyinda', 'prenom': 'Claire',
                'sexe': 'F', 'date_naissance': date(1990, 5, 12),
                'district': 'Mont-Ngafula', 'poids': 55.0,
            },
        )

    def _traitement(self, type_cas='NOUVEAU', date_debut=None, poids=55.0):
        return creer_traitement(
            medecin=self.medecin, patient=self.patient,
            donnees={
                'type_cas': type_cas,
                'date_debut': date_debut or date.today(),
                'poids_initial': poids,
                'unite_traitement': 'HGR Makala',
                'notes': '',
            },
        )

    # ---- Posologie et création de la fiche ----

    def test_posologie_par_bandes_de_poids(self):
        self.assertEqual(calculer_posologie(30), 2)
        self.assertEqual(calculer_posologie(37.5), 2)
        self.assertEqual(calculer_posologie(38), 3)
        self.assertEqual(calculer_posologie(54), 3)
        self.assertEqual(calculer_posologie(55), 4)
        self.assertEqual(calculer_posologie(70), 4)
        self.assertEqual(calculer_posologie(71), 5)
        self.assertIsNone(calculer_posologie(25))
        self.assertIsNone(calculer_posologie(None))

    def test_creation_fiche_nouveau_cas(self):
        traitement = self._traitement(poids=55.0)
        self.assertEqual(traitement.schema.code, '2RHZE/4RH')
        self.assertEqual(traitement.posologie_jour, 4)
        self.assertEqual(traitement.type_cas, 'NOUVEAU')
        self.assertTrue(traitement.est_en_cours)

    def test_creation_fiche_rechute_utilise_categorie_ii(self):
        traitement = self._traitement(type_cas='RECHUTE', poids=42.0)
        self.assertEqual(traitement.schema.categorie, 'RETRAITEMENT')
        self.assertEqual(traitement.posologie_jour, 3)

    def test_created_fiche_unique_par_patient(self):
        self._traitement()
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self._traitement()

    def test_fiche_impossible_si_poids_hors_bandes_mais_adaptable(self):
        traitement = self._traitement(poids=25.0)
        self.assertIsNone(traitement.posologie_jour)

    # ---- Observance journalière ----

    def test_enregistrement_observance(self):
        traitement = self._traitement()
        mois = enregistrer_observance(
            utilisateur=self.infirmier, traitement=traitement, mois=1,
            statuts_par_jour={'1': 'X', '2': '-', '3': 'O', '5': 'J'},
        )
        self.assertEqual(mois, 1)
        self.assertEqual(traitement.observances.count(), 4)
        self.assertTrue(
            traitement.observances.filter(jour=1, statut='X').exists()
        )
        self.assertIsNotNone(derniere_prise(traitement))

    def test_observance_mois_hors_limites_refusee(self):
        from django.core.exceptions import ValidationError
        traitement = self._traitement()
        with self.assertRaises(ValidationError):
            enregistrer_observance(
                utilisateur=self.infirmier, traitement=traitement, mois=20,
                statuts_par_jour={'1': 'X'},
            )

    def test_perdu_de_vue_detecte_apres_2_mois(self):
        traitement = self._traitement(date_debut=date.today() - timedelta(days=100))
        signalés = detecter_perdus_de_vue()
        self.assertIn(traitement, signalés)
        traitement.refresh_from_db()
        self.assertIsNotNone(traitement.perdu_de_vue)
        self.assertTrue(traitement.a_recuperer)
        self.assertTrue(
            Notification.objects.filter(destinataire=self.medecin).exists()
        )

    def test_reprise_de_prise_efface_perdu_de_vue(self):
        traitement = self._traitement(date_debut=date.today() - timedelta(days=100))
        detecter_perdus_de_vue()
        traitement.refresh_from_db()
        self.assertIsNotNone(traitement.perdu_de_vue)
        enregistrer_observance(
            utilisateur=self.infirmier, traitement=traitement, mois=1,
            statuts_par_jour={'1': 'X'},
        )
        traitement.refresh_from_db()
        self.assertIsNone(traitement.perdu_de_vue)

    # ---- Visite de suivi ----

    def test_enregistrement_visite_et_synchronisation_poids(self):
        traitement = self._traitement(poids=55.0)
        visite = enregistrer_visite(
            auteur=self.infirmier, traitement=traitement,
            donnees={
                'date': date.today(), 'poids': 57.0,
                'troubles_visuels': True, 'jaunisse': False,
                'eruption_cutanee': False, 'vertiges': False,
                'autres_effets': '', 'observations': 'Évolution favorable.',
            },
        )
        self.assertIn('Troubles visuels', visite.signes_alerte)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.poids, 57.0)
        traitement.refresh_from_db()
        self.assertEqual(traitement.poids_actuel, 57.0)

    # ---- Modification du traitement ----

    def test_modification_categorie_ii_avec_tracabilite(self):
        traitement = self._traitement(poids=55.0)
        modifier_traitement(
            medecin=self.medecin, traitement=traitement,
            donnees={
                'type_modification': 'CATEGORIE_II',
                'motif_medical': 'Rechute bactériologique confirmée.',
                'description': '',
            },
        )
        traitement.refresh_from_db()
        self.assertEqual(traitement.schema.categorie, 'RETRAITEMENT')
        historique = traitement.modifications_traitement.first()
        self.assertEqual(historique.ancien_schema.code, '2RHZE/4RH')
        self.assertEqual(historique.nouveau_schema.code, '2SRHZE/1RHZE/5RHE')
        self.assertEqual(historique.motif_medical, 'Rechute bactériologique confirmée.')

    def test_modification_motif_medical_obligatoire(self):
        from django.core.exceptions import ValidationError
        traitement = self._traitement()
        with self.assertRaises(ValidationError):
            modifier_traitement(
                medecin=self.medecin, traitement=traitement,
                donnees={'type_modification': 'SUSPENSION', 'motif_medical': ''},
            )
        self.assertFalse(traitement.modifications_traitement.exists())

    def test_modification_posologie(self):
        traitement = self._traitement(poids=55.0)
        modifier_traitement(
            medecin=self.medecin, traitement=traitement,
            donnees={
                'type_modification': 'POSOLOGIE',
                'motif_medical': 'Intolérance digestive, posologie réduite.',
                'nouveau_posologie_jour': 2,
            },
        )
        traitement.refresh_from_db()
        self.assertEqual(traitement.posologie_jour, 2)
        historique = traitement.modifications_traitement.first()
        self.assertEqual(historique.ancien_posologie_jour, 4)
        self.assertEqual(historique.nouveau_posologie_jour, 2)

    # ---- Rendez-vous (carte du malade) ----

    def test_rendez_vous_conflit_sur_meme_case(self):
        donnees = {
            'date': date.today() + timedelta(days=3), 'heure': time(10, 0),
            'type': 'CONTROLE', 'motif': '',
        }
        rdv, conflit = programmer_rendez_vous(
            auteur=self.infirmier, patient=self.patient, donnees=donnees,
        )
        self.assertFalse(conflit)
        autre_conflit, est_conflit = programmer_rendez_vous(
            auteur=self.infirmier, patient=self.patient, donnees=donnees,
        )
        self.assertTrue(est_conflit)
        self.assertEqual(autre_conflit.pk, rdv.pk)
        rdv3, est_conflit3 = programmer_rendez_vous(
            auteur=self.infirmier, patient=self.patient,
            donnees={**donnees, 'heure': time(11, 0)},
        )
        self.assertFalse(est_conflit3)

    def test_statut_rendez_vous_effectue(self):
        rdv, _ = programmer_rendez_vous(
            auteur=self.infirmier, patient=self.patient,
            donnees={
                'date': date.today() + timedelta(days=2), 'heure': time(9, 0),
                'type': 'C2', 'motif': '',
            },
        )
        statut_rendez_vous(
            utilisateur=self.infirmier, rendez_vous=rdv,
            nouveau_statut='EFFECTUE',
        )
        rdv.refresh_from_db()
        self.assertEqual(rdv.statut, 'EFFECTUE')

    # ---- Clôture et registre ----

    def test_cloture_traitement_issue_et_lecture_seule(self):
        from django.core.exceptions import ValidationError
        traitement = self._traitement()
        cloturer_traitement(
            medecin=self.medecin, traitement=traitement,
            issue_finale='GUERI', date_issue=date.today(),
        )
        traitement.refresh_from_db()
        self.assertEqual(traitement.statut, StatutTraitement.CLOTURE)
        self.assertEqual(traitement.get_issue_finale_display(), 'Guéri')
        self.assertEqual(traitement.cloture_par, self.medecin)
        with self.assertRaises(ValidationError):
            enregistrer_observance(
                utilisateur=self.infirmier, traitement=traitement, mois=1,
                statuts_par_jour={'1': 'X'},
            )

    def test_cohorte_guerison_du_trimestre(self):
        aujourdhui = date.today()
        t1 = self._traitement()
        cloturer_traitement(
            medecin=self.medecin, traitement=t1,
            issue_finale='GUERI', date_issue=aujourdhui,
        )
        autre_patient = creer_dossier_provisoire(
            medecin=self.medecin,
            donnees={
                'nom': 'Lutumba', 'prenom': 'Paul', 'sexe': 'M',
                'date_naissance': date(1985, 1, 1), 'poids': 48.0,
            },
        )
        creer_traitement(
            medecin=self.medecin, patient=autre_patient,
            donnees={
                'type_cas': 'NOUVEAU', 'date_debut': aujourdhui,
                'poids_initial': 48.0, 'unite_traitement': 'HGR Makala',
                'notes': '',
            },
        )
        trimestre = (aujourdhui.month - 1) // 3 + 1
        cohorte = cohorte_guerison(aujourdhui.year, trimestre)
        self.assertEqual(cohorte['total'], 2)
        self.assertEqual(cohorte['gueris'], 1)
        self.assertEqual(cohorte['taux'], 50.0)

    def test_bon_controle_doublon_detecte(self):
        creer_prescription_examen(
            medecin=self.medecin, patient=self.patient,
            donnees={
                'nature_echantillon': 'P', 'organe': '', 'motif': 'SUIVI',
                'mois_controle': 'C2', 'date_prelevement': date.today(),
                'statut_vih': '', 'observations': '',
            },
            types_examens=[TypeExamen.objects.get(code='BACILLOSCOPIE')],
        )
        self.assertIsNotNone(trouver_controle_en_attente(self.patient, 'C2'))
        self.assertIsNone(trouver_controle_en_attente(self.patient, 'C5'))

    # ---- Accès et vues ----

    def test_fiche_traitement_acces_roles(self):
        traitement = self._traitement()
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        response = self.client.get(
            reverse('traitement_fiche', kwargs={'pk': self.patient.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2RHZE/4RH')
        self.client.logout()
        self.client.login(username='inf.test@hgr-makala.cd', password='password123')
        response = self.client.get(
            reverse('traitement_fiche', kwargs={'pk': self.patient.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.client.logout()
        self.client.login(username='lab.test@hgr-makala.cd', password='password123')
        response = self.client.get(
            reverse('traitement_fiche', kwargs={'pk': self.patient.pk})
        )
        self.assertNotEqual(response.status_code, 200)

    def test_vue_creation_fiche_par_le_medecin(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        response = self.client.post(
            reverse('traitement_create', kwargs={'pk': self.patient.pk}),
            {
                'type_cas': 'NOUVEAU', 'date_debut': str(date.today()),
                'poids_initial': '55.0', 'unite_traitement': 'HGR Makala',
                'notes': '',
            },
        )
        self.assertRedirects(
            response,
            reverse('traitement_fiche', kwargs={'pk': self.patient.pk}),
        )
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.traitement.posologie_jour, 4)

    def test_vue_observance_post(self):
        traitement = self._traitement()
        self.client.login(username='inf.test@hgr-makala.cd', password='password123')
        donnees = {'mois': '1'}
        for jour in range(1, 6):
            donnees[f'jour_{jour}'] = 'X'
        response = self.client.post(
            reverse('traitement_observance', kwargs={'pk': self.patient.pk}),
            donnees,
        )
        self.assertRedirects(
            response,
            reverse('traitement_fiche', kwargs={'pk': self.patient.pk}) + '?mois=1',
        )
        self.assertEqual(traitement.observances.filter(mois=1).count(), 5)

    def test_vue_bon_controle_creation_et_doublon(self):
        bacillo = TypeExamen.objects.get(code='BACILLOSCOPIE')
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        donnees = {
            'mois_controle': 'C2',
            'examens': [bacillo.pk],
            'observations_cliniques': 'Contrôle du 2e mois.',
        }
        response = self.client.post(
            reverse('bon_controle', kwargs={'pk': self.patient.pk}), donnees,
        )
        self.assertRedirects(
            response,
            reverse('patient_detail', kwargs={'pk': self.patient.pk}),
        )
        self.assertTrue(
            ExamenPrescription.objects.filter(
                patient=self.patient, motif='SUIVI', mois_controle='C2'
            ).exists()
        )
        # Nouveau bon identique → rendu avec avertissement, pas de doublon créé.
        response = self.client.post(
            reverse('bon_controle', kwargs={'pk': self.patient.pk}), donnees,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'déjà en attente')
        self.assertEqual(
            ExamenPrescription.objects.filter(patient=self.patient).count(), 1
        )

    def test_vue_modifier_traitement_reservee_aux_medecins(self):
        self._traitement()
        self.client.login(username='inf.test@hgr-makala.cd', password='password123')
        response = self.client.get(
            reverse('traitement_modifier', kwargs={'pk': self.patient.pk})
        )
        self.assertRedirects(response, reverse('notification'))

    def test_vue_bon_controle_sans_traitement(self):
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        response = self.client.get(
            reverse('bon_controle', kwargs={'pk': self.patient.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bon de demande')

    def test_vue_carte_malade(self):
        self._traitement()
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        response = self.client.get(
            reverse('carte_malade', kwargs={'pk': self.patient.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Carte du malade')

    def test_vue_rendez_vous_conflit_message(self):
        self.client.login(username='inf.test@hgr-makala.cd', password='password123')
        donnees = {
            'date': str(date.today() + timedelta(days=4)), 'heure': '10:00',
            'type': 'CONTROLE', 'motif': '',
        }
        response = self.client.post(
            reverse('rendez_vous_create', kwargs={'pk': self.patient.pk}), donnees,
        )
        self.assertRedirects(
            response,
            reverse('carte_malade', kwargs={'pk': self.patient.pk}),
        )
        self.assertEqual(RendezVous.objects.count(), 1)
        # Même date et heure → conflit, pas de second rendez-vous.
        response = self.client.post(
            reverse('rendez_vous_create', kwargs={'pk': self.patient.pk}), donnees,
        )
        self.assertRedirects(
            response,
            reverse('carte_malade', kwargs={'pk': self.patient.pk}),
        )
        self.assertEqual(RendezVous.objects.count(), 1)

    def test_vue_cloture_dossier(self):
        traitement = self._traitement()
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        response = self.client.post(
            reverse('traitement_cloturer', kwargs={'pk': self.patient.pk}),
            {'issue_finale': 'TERMINE', 'date_issue': str(date.today())},
        )
        self.assertRedirects(
            response,
            reverse('traitement_fiche', kwargs={'pk': self.patient.pk}),
        )
        traitement.refresh_from_db()
        self.assertEqual(traitement.statut, StatutTraitement.CLOTURE)

    def test_vue_registre_cas(self):
        self._traitement()
        self.client.login(username='dr.test@hgr-makala.cd', password='password123')
        response = self.client.get(reverse('registre'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registre de cas de tuberculose')
        self.assertContains(response, 'Claire Kanyinda Mbuyi')
        self.assertContains(response, 'Nouveau cas')
