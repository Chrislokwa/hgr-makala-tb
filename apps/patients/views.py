import csv
import json
import time

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import DetailView, FormView, ListView, View

from .forms import (
    BonControleForm,
    CloturerTraitementForm,
    DossierProvisoireForm,
    InformationsAdministrativesForm,
    InterpretationForm,
    ModifierTraitementForm,
    ObservanceMoisForm,
    PrescriptionExamenForm,
    RendezVousForm,
    SaisieResultatForm,
    TraitementForm,
    VisiteSuiviForm,
)
from .models import (
    DecisionDiagnostic,
    ExamenPrescription,
    ModificationPatient,
    MotifExamen,
    NatureEchantillon,
    Notification,
    Patient,
    ResultatLabo,
    RendezVous,
    StatutDossier,
    StatutExamen,
    StatutRendezVous,
    StatutResultat,
    StatutTraitement,
    Traitement,
    TypeExamen,
)
from .permissions import (
    InfirmierRequiredMixin,
    LaborantinRequiredMixin,
    MedecinRequiredMixin,
    PersonnelAutoriseMixin,
)
from .services import (
    admission_est_finalisable,
    acquerir_verrou,
    bande_posologie_libelle,
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
    mois_traitement_libelle,
    programmer_rendez_vous,
    resultat_controle,
    statut_rendez_vous,
    statut_vih_patient,
    trouver_controle_en_attente,
    trouver_prescriptions_en_attente,
)


class PatientListView(PersonnelAutoriseMixin, ListView):
    model = Patient
    template_name = 'patients/patient_list.html'
    context_object_name = 'patients'
    paginate_by = 8

    def get_queryset(self):
        queryset = Patient.objects.all().order_by('-cree_le')
        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(ndp__icontains=q) |
                Q(nom__icontains=q) |
                Q(post_nom__icontains=q) |
                Q(prenom__icontains=q) |
                Q(telephone__icontains=q)
            )
        date_naissance = self.request.GET.get('date_naissance', '').strip()
        if date_naissance:
            queryset = queryset.filter(date_naissance=date_naissance)
        statut = self.request.GET.get('statut', '').strip()
        if statut in dict(StatutDossier.choices):
            queryset = queryset.filter(statut=statut)
        return queryset

    def get_template_names(self):
        # Requête HTMX (recherche / filtrage asynchrones) : fragment uniquement.
        if self.request.headers.get('HX-Request') == 'true':
            return ['patients/patient_list_results.html']
        return ['patients/patient_list.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'patients'
        context['q'] = self.request.GET.get('q', '').strip()
        context['date_naissance'] = self.request.GET.get('date_naissance', '').strip()
        context['statut_filter'] = self.request.GET.get('statut', '').strip()
        context['statut_choices'] = [('', 'Tous les statuts')] + list(StatutDossier.choices)
        context['patients_provisoires'] = Patient.objects.filter(
            statut=StatutDossier.PROVISOIRE
        ).count()
        context['patients_confirmes'] = Patient.objects.filter(
            statut=StatutDossier.CONFIRME
        ).count()
        return context


class PatientCreateView(MedecinRequiredMixin, FormView):
    template_name = 'patients/patient_create.html'
    form_class = DossierProvisoireForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'patients'
        return context

    def form_valid(self, form):
        donnees = form.cleaned_data
        doublon = Patient.trouver_doublon(
            donnees['nom'], donnees['prenom'], donnees['date_naissance']
        )
        if doublon:
            context = self.get_context_data(form=form)
            context['doublon'] = doublon
            return self.render_to_response(context)

        patient = creer_dossier_provisoire(medecin=self.request.user, donnees=donnees)
        if self.request.POST.get('action') == 'prescrire':
            messages.success(
                self.request,
                f"Dossier provisoire créé : {patient.ndp} · {patient.full_name}",
            )
            return redirect('prescription_create', pk=patient.pk)
        messages.success(
            self.request,
            f"Dossier provisoire créé : {patient.ndp} · {patient.full_name}",
        )
        return redirect('patient_detail', pk=patient.pk)


class AdmissionFinaliserView(InfirmierRequiredMixin, FormView):
    """US3.1 / UC1 — Finaliser l'admission administrative d'un patient.

    L'infirmier complète les données administratives (Nom, Post-nom,
    Prénom, Sexe, Date de naissance, Adresse, etc.) pour finaliser
    l'admission définitive. Garde-fou : diagnostic confirmé ET résultats
    de laboratoire saisis (Fonction 3).
    """

    template_name = 'patients/admission_confirm.html'
    form_class = InformationsAdministrativesForm

    def dispatch(self, request, *args, **kwargs):
        self.patient = get_object_or_404(Patient, pk=self.kwargs['pk'])
        if self.patient.admission_finalisee:
            messages.info(
                self.request,
                f"L'admission du dossier {self.patient.ndp} est déjà finalisée.",
            )
            return redirect('patient_detail', pk=self.patient.pk)
        if not admission_est_finalisable(self.patient):
            messages.error(
                self.request,
                "L'admission ne peut être finalisée qu'une fois le diagnostic "
                "confirmé et les résultats de laboratoire saisis.",
            )
            return redirect('patient_detail', pk=self.patient.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {
            champ: getattr(self.patient, champ)
            for champ in InformationsAdministrativesForm.Meta.fields
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'patients'
        context['patient'] = self.patient
        return context

    def form_valid(self, form):
        donnees = form.cleaned_data
        try:
            patient, doublon = finaliser_admission(
                infirmier=self.request.user,
                patient=self.patient,
                donnees=donnees,
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
            return self.form_invalid(form)

        if doublon:
            context = self.get_context_data(form=form)
            context['doublon'] = doublon
            return self.render_to_response(context)

        messages.success(
            self.request,
            f"Admission du dossier {patient.ndp} finalisée · {patient.full_name}.",
        )
        return redirect('patient_detail', pk=patient.pk)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class PatientAdminUpdateView(InfirmierRequiredMixin, FormView):
    """US3.2 / UC2 — Mettre à jour les informations administratives.

    L'infirmier modifie les données administratives (changement d'adresse,
    téléphone, correction d'une erreur de saisie). Chaque modification est
    historisée (date, heure, auteur). Le dossier est verrouillé pendant
    l'édition (UC2 / Ex1) : un second utilisateur est bloqué.
    """

    template_name = 'patients/patient_admin_update.html'
    form_class = InformationsAdministrativesForm

    def dispatch(self, request, *args, **kwargs):
        self.patient = get_object_or_404(Patient, pk=self.kwargs['pk'])
        verrou = acquerir_verrou(self.patient, request.user)
        if verrou is not None:
            messages.error(
                self.request,
                "Le dossier est temporairement verrouillé par "
                f"{verrou.utilisateur.titled_name}. Réessayez plus tard.",
            )
            return redirect('patient_detail', pk=self.patient.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {
            champ: getattr(self.patient, champ)
            for champ in InformationsAdministrativesForm.Meta.fields
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'patients'
        context['patient'] = self.patient
        return context

    def form_valid(self, form):
        mettre_a_jour_informations(
            infirmier=self.request.user,
            patient=self.patient,
            donnees=form.cleaned_data,
        )
        liberer_verrou(self.patient, self.request.user)
        messages.success(
            self.request,
            f"Informations du dossier {self.patient.ndp} mises à jour.",
        )
        return redirect('patient_detail', pk=self.patient.pk)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class PatientAdminAnnulerView(InfirmierRequiredMixin, View):
    """US3.2 / UC2 — Annule l'édition et libère le verrou du dossier."""

    def post(self, request, *args, **kwargs):
        self.patient = get_object_or_404(Patient, pk=self.kwargs['pk'])
        liberer_verrou(self.patient, request.user)
        messages.info(
            self.request,
            f"Modification du dossier {self.patient.ndp} annulée.",
        )
        return redirect('patient_detail', pk=self.patient.pk)


class PatientDetailView(PersonnelAutoriseMixin, DetailView):
    model = Patient
    template_name = 'patients/patient_detail.html'
    context_object_name = 'patient'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'patients'
        context['tab'] = self.request.GET.get('tab', 'signes')
        prescriptions = (
            self.object.examens_prescrits.all()
            .prefetch_related('examens')
        )
        paginator = Paginator(prescriptions, 8)
        page = self.request.GET.get('page', '1')
        context['page_obj'] = paginator.get_page(page)
        role = self.request.user.role
        # UC3 / Extension 4a : les informations sensibles (rapport médical,
        # interprétation) ne sont visibles que du médecin.
        context['peut_voir_rapport_medical'] = role == 'MEDECIN'
        context['peut_finaliser_admission'] = (
            role == 'INFIRMIER'
            and not self.object.admission_finalisee
            and admission_est_finalisable(self.object)
        )
        context['modifications'] = ModificationPatient.objects.filter(
            patient=self.object
        ).select_related('auteur')[:10]
        context['traitement'] = getattr(self.object, 'traitement', None)
        return context


class PrescriptionExamenCreateView(MedecinRequiredMixin, FormView):
    template_name = 'patients/prescription_create.html'
    form_class = PrescriptionExamenForm

    def dispatch(self, request, *args, **kwargs):
        self.patient = get_object_or_404(Patient, pk=self.kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'patients'
        context['patient'] = self.patient
        context['today'] = timezone.localdate()
        return context

    def get_initial(self):
        symptomes_respiratoires = (
            self.patient.signe_toux_persistante or self.patient.signe_hemoptysie
        )
        vih = TypeExamen.objects.filter(code='VIH').first()
        return {
            'nature_echantillon': (
                NatureEchantillon.PULMONAIRE if symptomes_respiratoires
                else NatureEchantillon.EXTRA_PULMONAIRE
            ),
            'motif': MotifExamen.DIAGNOSTIC,
            'examens': [vih.pk] if vih else [],
            'date_prelevement': timezone.localdate(),
        }

    def form_valid(self, form):
        donnees = form.cleaned_data
        codes_types = [t.code for t in donnees['examens']]
        en_attente = list(trouver_prescriptions_en_attente(self.patient, codes_types))
        if en_attente:
            context = self.get_context_data(form=form)
            context['doublon_prescriptions'] = en_attente
            return self.render_to_response(context)

        prescription = creer_prescription_examen(
            medecin=self.request.user,
            patient=self.patient,
            donnees={
                'nature_echantillon': donnees['nature_echantillon'],
                'organe': donnees['organe'],
                'motif': donnees['motif'],
                'mois_controle': donnees['mois_controle'],
                'date_prelevement': donnees['date_prelevement'],
                'statut_vih': donnees['statut_vih'],
                'observations': donnees['observations'],
            },
            types_examens=donnees['examens'],
        )
        messages.success(
            self.request,
            f"Demande {prescription.numero_demande} transmise au laboratoire "
            f"({prescription.types_libelles}).",
        )
        return redirect('patient_detail', pk=self.patient.pk)


class ExamenListView(LaborantinRequiredMixin, ListView):
    model = ExamenPrescription
    template_name = 'patients/examen_list.html'
    context_object_name = 'examens'
    paginate_by = 8

    def get_queryset(self):
        queryset = (
            ExamenPrescription.objects.all()
            .select_related('patient', 'medecin')
            .prefetch_related('examens')
        )
        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(numero_demande__icontains=q) |
                Q(patient__nom__icontains=q) |
                Q(patient__post_nom__icontains=q) |
                Q(patient__prenom__icontains=q) |
                Q(patient__ndp__icontains=q)
            )
        statut = self.request.GET.get('statut', '').strip()
        if statut in dict(StatutExamen.choices):
            queryset = queryset.filter(statut=statut)
        return queryset

    def get_template_names(self):
        # Requête HTMX (recherche / filtrage asynchrones) : fragment uniquement.
        if self.request.headers.get('HX-Request') == 'true':
            return ['patients/examen_list_results.html']
        return ['patients/examen_list.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'examens'
        context['q'] = self.request.GET.get('q', '').strip()
        context['statut_filter'] = self.request.GET.get('statut', '').strip()
        context['statut_choices'] = [('', 'Tous les statuts')] + list(StatutExamen.choices)
        context['nb_a_traiter'] = ExamenPrescription.objects.filter(
            statut=StatutExamen.EN_ATTENTE
        ).count()
        context['nb_disponibles'] = ExamenPrescription.objects.filter(
            statut=StatutExamen.RESULTATS_DISPONIBLES
        ).count()
        return context


class ExamenDetailView(LaborantinRequiredMixin, DetailView):
    model = ExamenPrescription
    template_name = 'patients/examen_detail.html'
    context_object_name = 'demande'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'examens'
        context['resultats'] = (
            self.object.resultats_labo.all()
            .select_related('laborantin')
        )
        context['deja_valide'] = ResultatLabo.objects.filter(
            prescription=self.object, statut=StatutResultat.VALIDE
        ).exists()
        return context


class SaisieResultatView(LaborantinRequiredMixin, FormView):
    template_name = 'patients/resultat_form.html'
    form_class = SaisieResultatForm

    def dispatch(self, request, *args, **kwargs):
        self.demande = get_object_or_404(ExamenPrescription, pk=self.kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'examens'
        context['demande'] = self.demande
        context['codes_examens'] = set(
            self.demande.examens.values_list('code', flat=True)
        )
        context['deja_valide'] = ResultatLabo.objects.filter(
            prescription=self.demande, statut=StatutResultat.VALIDE
        ).exists()
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['prescription'] = self.demande
        return kwargs

    def get_initial(self):
        dernier = self.demande.resultat_recent
        if dernier is None:
            return {}
        return {
            champ: getattr(dernier, champ)
            for champ in SaisieResultatForm.Meta.fields
            if getattr(dernier, champ) not in (None, '')
        }

    def form_valid(self, form):
        valider = self.request.POST.get('action') == 'valider'
        donnees = form.cleaned_data
        enregistrer_resultats(
            laborantin=self.request.user,
            prescription=self.demande,
            donnees=donnees,
            valider=valider,
        )
        if valider:
            messages.success(
                self.request,
                f"Résultats validés et mis à disposition du médecin "
                f"({self.demande.numero_demande}).",
            )
        else:
            messages.info(
                self.request,
                f"Résultats enregistrés en brouillon "
                f"({self.demande.numero_demande}).",
            )
        return redirect('examen_detail', pk=self.demande.pk)


class ConsultationResultatView(MedecinRequiredMixin, DetailView):
    """UC5 — Consulter les résultats d'un examen.

    Le médecin ouvre le dossier du patient, accède à la section « Examens »
    puis sélectionne l'examen dont le statut est « Résultats disponibles ».
    La page affiche la demande et les résultats validés, sans modification.
    """

    model = ExamenPrescription
    template_name = 'patients/consultation_resultat.html'
    context_object_name = 'demande'

    def dispatch(self, request, *args, **kwargs):
        self.demande = get_object_or_404(
            ExamenPrescription,
            pk=self.kwargs['prescription_pk'],
            patient_id=self.kwargs['pk'],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.demande

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'patients'
        context['resultat'] = self.demande.resultat_valide
        context['interpretation'] = self.demande.interpretation
        return context


class InterpretationResultatView(MedecinRequiredMixin, FormView):
    """UC6 — Interpréter les résultats.

    Le médecin, après avoir consulté les résultats (UC5), sélectionne
    l'option « Interpréter les résultats ». Le système affiche un formulaire
    reprenant les résultats, puis enregistre l'analyse et déclenche le point
    d'extension « Décision de diagnostic » (UC7 / UC8 selon la décision).
    """

    template_name = 'patients/interpretation_form.html'
    form_class = InterpretationForm

    def dispatch(self, request, *args, **kwargs):
        self.demande = get_object_or_404(
            ExamenPrescription,
            pk=self.kwargs['prescription_pk'],
            patient_id=self.kwargs['pk'],
        )
        if self.demande.statut != StatutExamen.RESULTATS_DISPONIBLES:
            messages.info(
                self.request,
                "Les résultats ne sont pas encore disponibles pour cette demande : "
                "l'interprétation n'est possible qu'une fois les analyses validées.",
            )
            return redirect('consultation_resultat', pk=self.demande.patient_id,
                            prescription_pk=self.demande.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'patients'
        context['demande'] = self.demande
        context['resultat'] = self.demande.resultat_valide
        context['interpretation'] = self.demande.interpretation
        return context

    def get_initial(self):
        interpretation = self.demande.interpretation
        if interpretation is None:
            return {}
        return {
            'interpretation': interpretation.interpretation,
            'observations': interpretation.observations,
            'decision': interpretation.decision,
        }

    def form_valid(self, form):
        donnees = form.cleaned_data
        enregistrer_interpretation(
            medecin=self.request.user,
            prescription=self.demande,
            donnees={
                'interpretation': donnees['interpretation'],
                'observations': donnees['observations'],
                'decision': donnees['decision'],
            },
        )
        if donnees['decision'] == DecisionDiagnostic.CONFIRMEE:
            messages.success(
                self.request,
                f"Tuberculose confirmée — le dossier {self.demande.patient.ndp} "
                f"est validé pour l'admission.",
            )
        else:
            messages.info(
                self.request,
                f"Tuberculose infirmée — l'admission du dossier "
                f"{self.demande.patient.ndp} a été annulée.",
            )
        return redirect('consultation_resultat', pk=self.demande.patient_id,
                        prescription_pk=self.demande.pk)


class NotificationMarquerLuesView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        request.user.notifications.filter(lu=False).update(lu=True)
        return redirect('notification')


class NotificationSseView(LoginRequiredMixin, View):
    """Flux SSE des notifications de l'utilisateur connecté.

    Le navigateur reste connecté ; chaque nouvelle notification est poussée
    en temps réel (sans rechargement) sous la forme d'un événement
    `notification`. La détection repose sur un polling BD léger côté serveur.
    """

    def get(self, request, *args, **kwargs):
        response = StreamingHttpResponse(
            self._event_stream(request.user),
            content_type='text/event-stream',
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    def _event_stream(self, user):
        dernier_id = (
            Notification.objects.filter(destinataire=user)
            .order_by('-pk')
            .values_list('pk', flat=True)
            .first() or 0
        )
        while True:
            nouvelles = list(
                Notification.objects.filter(destinataire=user, pk__gt=dernier_id)
                .select_related('destinataire')
            )
            for notif in nouvelles:
                payload = {
                    'id': notif.pk,
                    'message': notif.message,
                    'url': notif.url or '/notification/',
                    'cree_le': notif.cree_le.isoformat(),
                    'non_lues': user.notifications.filter(lu=False).count(),
                }
                yield f"event: notification\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                dernier_id = notif.pk
            yield ": keepalive\n\n"
            time.sleep(3)


# ---------------------------------------------------------------------------
# Epic 4 — Suivi thérapeutique (US4.1, US4.2, US4.3)
# ---------------------------------------------------------------------------


class TraitementCreateView(MedecinRequiredMixin, FormView):
    """US4.1 — Crée la fiche de traitement antituberculeux du patient."""

    template_name = 'patients/traitement_create.html'
    form_class = TraitementForm

    def dispatch(self, request, *args, **kwargs):
        self.patient = get_object_or_404(Patient, pk=self.kwargs['pk'])
        if hasattr(self.patient, 'traitement'):
            messages.info(
                self.request,
                f"Le dossier {self.patient.ndp} a déjà une fiche de traitement.",
            )
            return redirect('traitement_fiche', pk=self.patient.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['patient'] = self.patient
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'patients'
        context['patient'] = self.patient
        return context

    def form_valid(self, form):
        try:
            traitement = creer_traitement(
                medecin=self.request.user,
                patient=self.patient,
                donnees=form.cleaned_data,
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
            return self.form_invalid(form)
        messages.success(
            self.request,
            f"Fiche de traitement créée · {traitement.schema.code} — "
            f"posologie {traitement.posologie_jour or '≤ адаптер'} c/j.",
        )
        return redirect('traitement_fiche', pk=self.patient.pk)


class FicheTraitementView(PersonnelAutoriseMixin, DetailView):
    """US4.1 — Fiche de traitement : schéma (Zone 1), observance (Zone 2),
    suivi clinique et historique des modifications (Zone 3)."""

    model = Traitement
    template_name = 'patients/traitement_fiche.html'
    context_object_name = 'traitement'

    def get_object(self, queryset=None):
        return get_object_or_404(Traitement, patient_id=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        detecter_perdus_de_vue()
        traitement = self.object
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'patients'
        context['patient'] = traitement.patient
        context['total_mois'] = traitement.schema.duree_totale_mois
        mois = int(self.request.GET.get('mois', 1) or 1)
        mois = max(1, min(mois, context['total_mois']))
        context['mois'] = mois
        context['mois_label'] = mois_traitement_libelle(traitement, mois)
        context['observ_form'] = ObservanceMoisForm(
            traitement=traitement, mois=mois,
        )
        context['visite_form'] = VisiteSuiviForm()
        context['derniere_prise'] = derniere_prise(traitement)
        context['bande_posologie'] = bande_posologie_libelle(traitement.poids_initial)
        context['visites'] = traitement.visites.select_related('cree_par')[:8]
        context['modifications'] = (
            traitement.modifications_traitement
            .select_related('medecin', 'ancien_schema', 'nouveau_schema')[:10]
        )
        context['observance_par_mois'] = {
            mois_idx: {
                obs.jour: obs.statut
                for obs in traitement.observances.filter(mois=mois_idx)
            }
            for mois_idx in range(1, context['total_mois'] + 1)
        }
        return context


class ObservanceSaisieView(PersonnelAutoriseMixin, FormView):
    """US4.1 — Enregistre la grille d'observance mensuelle (codes X/-/O/↑)."""

    form_class = ObservanceMoisForm
    http_method_names = ['post']

    def dispatch(self, request, *args, **kwargs):
        self.traitement = get_object_or_404(Traitement, patient_id=self.kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        mois = int(self.request.POST.get('mois', 1) or 1)
        kwargs = super().get_form_kwargs()
        kwargs['traitement'] = self.traitement
        kwargs['mois'] = mois
        return kwargs

    def form_valid(self, form):
        try:
            mois = enregistrer_observance(
                utilisateur=self.request.user,
                traitement=self.traitement,
                mois=int(form.cleaned_data['mois']),
                statuts_par_jour=form.statuts_par_jour,
            )
        except ValidationError as exc:
            messages.error(self.request, exc.message)
            return redirect(
                'traitement_fiche', pk=self.traitement.patient_id
            )
        messages.success(
            self.request,
            f"Observance du mois {mois} enregistrée pour "
            f"{self.traitement.patient.ndp}.",
        )
        from django.urls import reverse
        return redirect(
            f"{reverse('traitement_fiche', kwargs={'pk': self.traitement.patient_id})}?mois={mois}"
        )

    def form_invalid(self, form):
        messages.error(self.request, "Grille d'observance invalide.")
        return redirect('traitement_fiche', pk=self.traitement.patient_id)


class VisiteSuiviCreateView(PersonnelAutoriseMixin, FormView):
    """US4.1 — Zone 3 : ajoute une visite de suivi (poids, signes d'alerte)."""

    form_class = VisiteSuiviForm
    http_method_names = ['post']

    def dispatch(self, request, *args, **kwargs):
        self.traitement = get_object_or_404(Traitement, patient_id=self.kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            enregistrer_visite(
                auteur=self.request.user,
                traitement=self.traitement,
                donnees=form.cleaned_data,
            )
        except ValidationError as exc:
            messages.error(self.request, exc.message)
        else:
            messages.success(
                self.request,
                f"Visite de suivi enregistrée ({self.traitement.patient.ndp}).",
            )
        return redirect('traitement_fiche', pk=self.traitement.patient_id)

    def form_invalid(self, form):
        messages.error(self.request, "Visite invalide : vérifiez la date et le poids.")
        return redirect('traitement_fiche', pk=self.traitement.patient_id)


class ModifierTraitementView(MedecinRequiredMixin, FormView):
    """US4.1 — Modification du traitement (Catégorie II, suspension,
    posologie) avec motif médical obligatoire et traçabilité."""

    template_name = 'patients/modifier_traitement.html'
    form_class = ModifierTraitementForm

    def dispatch(self, request, *args, **kwargs):
        self.traitement = get_object_or_404(Traitement, patient_id=self.kwargs['pk'])
        if self.traitement.statut != StatutTraitement.EN_COURS:
            messages.error(self.request, "Ce traitement est clôturé : aucune modification possible.")
            return redirect('traitement_fiche', pk=self.traitement.patient_id)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'patients'
        context['patient'] = self.traitement.patient
        context['traitement'] = self.traitement
        context['bande_posologie'] = bande_posologie_libelle(
            self.traitement.poids_actuel
        )
        return context

    def form_valid(self, form):
        try:
            modifier_traitement(
                medecin=self.request.user,
                traitement=self.traitement,
                donnees=form.cleaned_data,
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
            return self.form_invalid(form)
        messages.success(
            self.request,
            "Modification du traitement enregistrée.",
        )
        return redirect('traitement_fiche', pk=self.traitement.patient_id)


class BonControleView(MedecinRequiredMixin, FormView):
    """US4.2 — Bon de demande d'examen de laboratoire de contrôle
    (C2, C3, C4, C5, C6, fin de traitement)."""

    template_name = 'patients/bon_controle.html'
    form_class = BonControleForm

    def dispatch(self, request, *args, **kwargs):
        self.patient = get_object_or_404(Patient, pk=self.kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['patient'] = self.patient
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'patients'
        context['patient'] = self.patient
        context['traitement'] = getattr(self.patient, 'traitement', None)
        context['today'] = timezone.localdate()
        return context

    def form_valid(self, form):
        donnees = form.cleaned_data
        mois_controle = donnees['mois_controle']
        en_attente = trouver_controle_en_attente(self.patient, mois_controle)
        if en_attente is not None:
            context = self.get_context_data(form=form)
            context['controle_en_attente'] = en_attente
            return self.render_to_response(context)

        prescription = creer_prescription_examen(
            medecin=self.request.user,
            patient=self.patient,
            donnees={
                'nature_echantillon': NatureEchantillon.PULMONAIRE,
                'organe': '',
                'motif': MotifExamen.SUIVI_CONTROLE,
                'mois_controle': mois_controle,
                'date_prelevement': timezone.localdate(),
                'statut_vih': '',
                'observations': donnees.get('observations_cliniques', ''),
            },
            types_examens=donnees['examens'],
        )
        messages.success(
            self.request,
            f"Bon de contrôle {prescription.numero_demande} transmis au "
            f"laboratoire ({prescription.types_libelles}).",
        )
        return redirect('patient_detail', pk=self.patient.pk)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class CarteDuMaladeView(PersonnelAutoriseMixin, DetailView):
    """US4.3 — Carte du malade : identité, rendez-vous, résultats simples."""

    model = Patient
    template_name = 'patients/carte_malade.html'
    context_object_name = 'patient'

    def get_context_data(self, **kwargs):
        detecter_perdus_de_vue()
        context = super().get_context_data(**kwargs)
        patient = self.object
        context['active_nav'] = 'patients'
        context['traitement'] = getattr(patient, 'traitement', None)
        context['rendez_vous'] = patient.rendez_vous.all()[:15]
        context['rdv_form'] = RendezVousForm()
        context['statut_vih'], context['vih_positif'] = statut_vih_patient(patient)
        resultats = (
            ExamenPrescription.objects
            .filter(patient=patient, statut=StatutExamen.RESULTATS_DISPONIBLES)
            .select_related('medecin')
            .prefetch_related('examens')
            [:6]
        )
        context['resultats_recents'] = resultats
        return context


class RendezVousCreateView(PersonnelAutoriseMixin, FormView):
    """US4.3 — Planifie un rendez-vous (agenda partagé, sans conflit)."""

    form_class = RendezVousForm
    http_method_names = ['post']

    def dispatch(self, request, *args, **kwargs):
        self.patient = get_object_or_404(Patient, pk=self.kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        rendez_vous, conflit = programmer_rendez_vous(
            auteur=self.request.user,
            patient=self.patient,
            donnees=form.cleaned_data,
        )
        if conflit:
            messages.error(
                self.request,
                f"Case occupée : un rendez-vous existe déjà le "
                f"{rendez_vous.date:%d/%m/%Y} à {rendez_vous.heure:%H:%M} "
                f"pour {rendez_vous.patient.full_name}.",
            )
            return redirect('carte_malade', pk=self.patient.pk)
        messages.success(
            self.request,
            f"Rendez-vous planifié le {rendez_vous.date:%d/%m/%Y} à "
            f"{rendez_vous.heure:%H:%M}.",
        )
        return redirect('carte_malade', pk=self.patient.pk)

    def form_invalid(self, form):
        messages.error(self.request, "Rendez-vous invalide : vérifiez la date et l'heure.")
        return redirect('carte_malade', pk=self.patient.pk)


class RendezVousStatutView(PersonnelAutoriseMixin, View):
    """US4.3 — Marque un rendez-vous comme effectué ou annulé."""

    def post(self, request, *args, **kwargs):
        rendez_vous = get_object_or_404(RendezVous, pk=self.kwargs['pk'])
        action = request.POST.get('action')
        nouveau_statut = (
            StatutRendezVous.EFFECTUE if action == 'effectuer'
            else StatutRendezVous.ANNULE if action == 'annuler'
            else None
        )
        try:
            statut_rendez_vous(
                utilisateur=request.user,
                rendez_vous=rendez_vous,
                nouveau_statut=nouveau_statut,
            )
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(
                request,
                f"Rendez-vous du {rendez_vous.date:%d/%m/%Y} "
                f"marqué « {rendez_vous.get_statut_display()} ».",
            )
        return redirect('carte_malade', pk=rendez_vous.patient_id)


class RegistreView(PersonnelAutoriseMixin, ListView):
    """Registre de cas de tuberculose : suivi, issues et cohorte."""

    model = Traitement
    template_name = 'patients/registre.html'
    context_object_name = 'registre'
    paginate_by = 12

    def get_queryset(self):
        detecter_perdus_de_vue()
        queryset = (
            Traitement.objects.all()
            .select_related('patient', 'schema', 'cree_par', 'cloture_par')
        )
        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(patient__ndp__icontains=q) |
                Q(patient__nom__icontains=q) |
                Q(patient__post_nom__icontains=q) |
                Q(patient__prenom__icontains=q)
            )
        unite = self.request.GET.get('unite', '').strip()
        if unite:
            queryset = queryset.filter(unite_traitement=unite)
        date_debut = self.request.GET.get('date_debut', '').strip()
        if date_debut:
            queryset = queryset.filter(date_debut=date_debut)
        statut = self.request.GET.get('statut', '').strip()
        if statut in dict(StatutTraitement.choices):
            queryset = queryset.filter(statut=statut)
        if statut == 'PERDU_DE_VUE':
            queryset = queryset.filter(perdu_de_vue__isnull=False)
        return queryset.order_by('-date_debut', '-cree_le')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        detecter_perdus_de_vue()
        context['active_nav'] = 'registre'
        context['q'] = self.request.GET.get('q', '').strip()
        context['unite_filter'] = self.request.GET.get('unite', '').strip()
        context['date_debut'] = self.request.GET.get('date_debut', '').strip()
        context['statut_filter'] = self.request.GET.get('statut', '').strip()
        context['statut_choices'] = [('', 'Tous les statuts')] + list(StatutTraitement.choices) + [
            ('PERDU_DE_VUE', 'Perdu de vue (à récupérer)'),
        ]
        context['unites'] = (
            Traitement.objects.values_list('unite_traitement', flat=True)
            .distinct().order_by('unite_traitement')
        )
        annee = int(self.request.GET.get('annee', '') or timezone.localdate().year)
        trimestre = int(self.request.GET.get('trimestre', '1') or 1)
        context['cohorte'] = cohorte_guerison(annee, max(1, min(trimestre, 4)))
        context['cohorte_annee'] = annee
        context['cohorte_trimestre'] = max(1, min(trimestre, 4))

        def _libelle_resultat(prescription, resultat):
            if resultat is None:
                return 'En attente'
            parties = []
            if resultat.echantillon_1:
                parties.append(f"É1 {resultat.get_echantillon_1_display()}")
            if resultat.echantillon_2:
                parties.append(f"É2 {resultat.get_echantillon_2_display()}")
            if resultat.resultat_genexpert:
                parties.append(f"GX {resultat.get_resultat_genexpert_display()}")
            return ' · '.join(parties) or resultat.get_statut_display()

        resultats = {}
        statuts_vih = {}
        for traitement in context['registre']:
            for code in ('C2', 'C5'):
                prescription, resultat = resultat_controle(traitement.patient, code)
                resultats[(traitement.pk, code)] = (
                    prescription, _libelle_resultat(prescription, resultat)
                )
            statuts_vih[traitement.pk] = statut_vih_patient(traitement.patient)
        context['resultats_controle'] = resultats
        context['statuts_vih'] = statuts_vih
        return context

    def get_template_names(self):
        if self.request.headers.get('HX-Request') == 'true':
            return ['patients/registre_results.html']
        return ['patients/registre.html']


class RegistreExportView(PersonnelAutoriseMixin, View):
    """Registre de cas — Export CSV (compatible tableur)."""

    def get(self, request, *args, **kwargs):
        queryset = (
            Traitement.objects.all()
            .select_related('patient', 'schema', 'cloture_par')
            .order_by('-date_debut', '-cree_le')
        )
        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(patient__ndp__icontains=q) |
                Q(patient__nom__icontains=q) |
                Q(patient__post_nom__icontains=q) |
                Q(patient__prenom__icontains=q)
            )
        unite = self.request.GET.get('unite', '').strip()
        if unite:
            queryset = queryset.filter(unite_traitement=unite)
        date_debut = self.request.GET.get('date_debut', '').strip()
        if date_debut:
            queryset = queryset.filter(date_debut=date_debut)
        statut = self.request.GET.get('statut', '').strip()
        if statut in dict(StatutTraitement.choices):
            queryset = queryset.filter(statut=statut)
        if statut == 'PERDU_DE_VUE':
            queryset = queryset.filter(perdu_de_vue__isnull=False)

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="registre_cas_{timezone.localdate():%Y%m%d}.csv"'
        )
        response.write('\ufeff')
        writer = csv.writer(response, delimiter=';')
        writer.writerow([
            'NDP', 'Patient', 'Sexe', 'Âge', 'Date début', 'Type de cas',
            'Schéma', 'Posologie (c/j)', 'Unité de traitement',
            'Poids actuel (kg)', 'Statut VIH', 'Résultat C2', 'Résultat C5',
            'Issue finale', 'Date issue', 'Statut', 'Date dernière prise',
        ])
        for traitement in queryset:
            patient = traitement.patient
            presc_c2, res_c2 = resultat_controle(patient, 'C2')
            presc_c5, res_c5 = resultat_controle(patient, 'C5')
            _lib = lambda r: (
                'En attente' if r is None else (
                    ' · '.join(filter(None, [
                        f"É1 {r.get_echantillon_1_display()}" if r.echantillon_1 else '',
                        f"É2 {r.get_echantillon_2_display()}" if r.echantillon_2 else '',
                        f"GX {r.get_resultat_genexpert_display()}" if r.resultat_genexpert else '',
                    ])) or r.get_statut_display()
                )
            )
            vih, _ = statut_vih_patient(patient)
            derniere = derniere_prise(traitement)
            writer.writerow([
                patient.ndp, patient.full_name, patient.get_sexe_display(),
                patient.age or '', traitement.date_debut,
                traitement.get_type_cas_display(), traitement.schema.code,
                traitement.posologie_jour or '', traitement.unite_traitement,
                traitement.poids_actuel or '', vih,
                _lib(res_c2), _lib(res_c5),
                traitement.get_issue_finale_display() if traitement.issue_finale else '',
                f"{traitement.issue_decision_date:%d/%m/%Y}" if traitement.issue_decision_date else '',
                traitement.get_statut_display(),
                f"{derniere:%d/%m/%Y}" if derniere else '',
            ])
        return response


class TraitementCloturerView(MedecinRequiredMixin, FormView):
    """Registre de cas — Issue finale et clôture (archive en lecture seule)."""

    template_name = 'patients/traitement_cloture.html'
    form_class = CloturerTraitementForm

    def dispatch(self, request, *args, **kwargs):
        self.traitement = get_object_or_404(Traitement, patient_id=self.kwargs['pk'])
        if self.traitement.statut != StatutTraitement.EN_COURS:
            messages.info(self.request, "Ce dossier est déjà clôturé.")
            return redirect('traitement_fiche', pk=self.traitement.patient_id)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'registre'
        context['patient'] = self.traitement.patient
        context['traitement'] = self.traitement
        return context

    def form_valid(self, form):
        cloturer_traitement(
            medecin=self.request.user,
            traitement=self.traitement,
            issue_finale=form.cleaned_data['issue_finale'],
            date_issue=form.cleaned_data['date_issue'],
        )
        messages.success(
            self.request,
            f"Dossier {self.traitement.patient.ndp} clôturé — "
            f"{self.traitement.get_issue_finale_display()}.",
        )
        return redirect('traitement_fiche', pk=self.traitement.patient_id)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))