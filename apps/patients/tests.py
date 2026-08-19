from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from apps.users.models import CustomUser, UserRole

from .models import ExamenPrescription, Patient, StatutDossier, StatutExamen, TypeExamen
from .services import creer_dossier_provisoire, creer_prescription_examen


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

    def test_patient_list_requires_medecin(self):
        self.client.login(username='inf.test@hgr-makala.cd', password='password123')
        response = self.client.get(reverse('patient_list'))
        self.assertRedirects(response, reverse('dashboard'))

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

    def test_patient_detail_other_role_denied(self):
        self.client.login(username='inf.test@hgr-makala.cd', password='password123')
        patient = creer_dossier_provisoire(
            medecin=self.medecin,
            donnees={
                'nom': 'Mbuyi', 'prenom': 'Claire', 'sexe': 'F',
                'date_naissance': date(1990, 5, 12),
            },
        )
        response = self.client.get(reverse('patient_detail', kwargs={'pk': patient.pk}))
        self.assertRedirects(response, reverse('dashboard'))


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
        self.assertRedirects(response, reverse('dashboard'))

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