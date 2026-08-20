import json
import time

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import DetailView, FormView, ListView, View

from .forms import (
    DossierProvisoireForm,
    InformationsAdministrativesForm,
    InterpretationForm,
    PrescriptionExamenForm,
    SaisieResultatForm,
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
    StatutDossier,
    StatutExamen,
    StatutResultat,
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
    creer_dossier_provisoire,
    creer_prescription_examen,
    enregistrer_interpretation,
    enregistrer_resultats,
    finaliser_admission,
    liberer_verrou,
    mettre_a_jour_informations,
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