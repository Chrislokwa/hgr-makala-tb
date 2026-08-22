import json
import time

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
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
)
from .permissions import (
    InfirmierRequiredMixin,
    LaborantinRequiredMixin,
    MedecinRequiredMixin,
    PersonnelAutoriseMixin,
)
from .services import (
    acquerir_verrou,
    bande_posologie_libelle,
    cloturer_traitement,
    creer_dossier_provisoire,
    creer_prescription_examen,
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
    statut_rendez_vous,
    trouver_controle_en_attente,
    trouver_prescriptions_en_attente,
)


class PatientListView(PersonnelAutoriseMixin, ListView):
    model = Patient
    template_name = 'patients/patient_list.html'
    context_object_name = 'patients'
    paginate_by = 8

    def get_queryset(self):
        queryset = Patient.objects.select_related('cree_par').prefetch_related('traitement').all().order_by('-cree_le')
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
        context['patients_en_traitement'] = Patient.objects.filter(
            statut=StatutDossier.EN_TRAITEMENT
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
        donnees = dict(form.cleaned_data)
        notes_traitement = donnees.pop('notes_traitement', '')
        doublon = Patient.trouver_doublon(
            donnees['nom'], donnees['prenom'], donnees['date_naissance']
        )
        if doublon:
            context = self.get_context_data(form=form)
            context['doublon'] = doublon
            return self.render_to_response(context)

        patient = creer_dossier_provisoire(
            medecin=self.request.user,
            donnees={**donnees, 'notes': notes_traitement},
        )
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
    Prénom, Sexe, Date de naissance, Adresse, etc.) puis valide
    l'admission : le dossier passe au statut « En traitement », le schéma
    thérapeutique ayant déjà été prescrit à la création du dossier.
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
        if self.patient.statut == StatutDossier.PROVISOIRE:
            messages.error(
                request,
                "Dossier provisoire : finalisez l'admission avant toute modification.",
            )
            return redirect('patient_detail', pk=self.patient.pk)
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
            role == 'INFIRMIER' and not self.object.admission_finalisee
        )
        context['is_provisoire'] = self.object.statut == StatutDossier.PROVISOIRE
        context['modifications'] = ModificationPatient.objects.filter(
            patient=self.object
        ).select_related('auteur')[:10]
        context['traitement'] = getattr(self.object, 'traitement', None)
        return context


class PrescriptionExamenCreateView(MedecinRequiredMixin, FormView):
    template_name = 'examens/prescription_create.html'
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
        return {
            'nature_echantillon': (
                NatureEchantillon.PULMONAIRE if symptomes_respiratoires
                else NatureEchantillon.EXTRA_PULMONAIRE
            ),
            'motif': MotifExamen.DIAGNOSTIC,
            'examens': [],
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
    template_name = 'examens/examen_list.html'
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
            return ['examens/examen_list_results.html']
        return ['examens/examen_list.html']

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
    template_name = 'examens/examen_detail.html'
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
    template_name = 'examens/resultat_form.html'
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
        donnees = form.cleaned_data
        enregistrer_resultats(
            laborantin=self.request.user,
            prescription=self.demande,
            donnees=donnees,
        )
        messages.success(
            self.request,
            f"Résultats validés et mis à disposition du médecin "
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
    template_name = 'examens/consultation_resultat.html'
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

    template_name = 'examens/interpretation_form.html'
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


class NotificationOpenView(LoginRequiredMixin, View):
    """Ouvre une notification et la marque comme lue directement au clic."""

    def get(self, request, *args, **kwargs):
        notification = get_object_or_404(
            Notification, pk=self.kwargs['pk'], destinataire=request.user
        )
        if not notification.lu:
            notification.lu = True
            notification.save(update_fields=['lu'])
        target = notification.url or '/notification/'
        return redirect(target)


class NotificationMarquerLuesView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        request.user.notifications.filter(lu=False).update(lu=True)
        return redirect('notification')


class NotificationSupprimerView(LoginRequiredMixin, View):
    """Supprime une seule notification de l'utilisateur connecté."""

    def post(self, request, *args, **kwargs):
        notification = get_object_or_404(
            Notification, pk=self.kwargs['pk'], destinataire=request.user
        )
        notification.delete()
        messages.success(request, "Notification supprimée.")
        return redirect('notification')


class NotificationViderView(LoginRequiredMixin, View):
    """Vide toutes les notifications après confirmation explicite."""

    template_name = 'authentication/notifications_vider.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {
            'active_nav': 'notifications',
            'total': request.user.notifications.count(),
        })

    def post(self, request, *args, **kwargs):
        request.user.notifications.all().delete()
        messages.success(request, "Toutes vos notifications ont été supprimées.")
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
                    'total': user.notifications.count(),
                }
                yield f"event: notification\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                dernier_id = notif.pk
            yield ": keepalive\n\n"
            time.sleep(3)


# ---------------------------------------------------------------------------
# Epic 4 — Suivi thérapeutique (US4.1 / US4.2 / US4.3)
# ---------------------------------------------------------------------------


class FicheTraitementView(PersonnelAutoriseMixin, DetailView):
    """US4.1 — Fiche de traitement : schéma (Zone 1), observance (Zone 2),
    suivi clinique et historique des modifications (Zone 3)."""

    model = Traitement
    template_name = 'treatment/traitement_fiche.html'
    context_object_name = 'traitement'

    def dispatch(self, request, *args, **kwargs):
        traitement = get_object_or_404(Traitement, patient_id=self.kwargs['pk'])
        if traitement.patient.statut == StatutDossier.PROVISOIRE:
            messages.error(request, "Dossier provisoire : finalisez l'admission avant d'accéder à la fiche de traitement.")
            return redirect('patient_detail', pk=traitement.patient_id)
        return super().dispatch(request, *args, **kwargs)

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


class ObservanceSaisieView(InfirmierRequiredMixin, FormView):
    """US4.1 — Enregistre la grille d'observance mensuelle (codes X/-/O/↑).

    Le suivi thérapeutique (observance, visites) est réservé à l'infirmier.
    """

    form_class = ObservanceMoisForm
    http_method_names = ['post']

    def dispatch(self, request, *args, **kwargs):
        self.traitement = get_object_or_404(Traitement, patient_id=self.kwargs['pk'])
        if self.traitement.patient.statut == StatutDossier.PROVISOIRE:
            messages.error(request, "Dossier provisoire : finalisez l'admission avant de saisir l'observance.")
            return redirect('patient_detail', pk=self.traitement.patient_id)
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


class VisiteSuiviCreateView(InfirmierRequiredMixin, FormView):
    """US4.1 — Visite de contrôle dans sa propre interface (point 9).

    GET affiche le formulaire dédié ; POST enregistre la visite.
    """

    form_class = VisiteSuiviForm
    template_name = 'treatment/visite_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.traitement = get_object_or_404(Traitement, patient_id=self.kwargs['pk'])
        if self.traitement.patient.statut == StatutDossier.PROVISOIRE:
            messages.error(request, "Dossier provisoire : finalisez l'admission avant d'enregistrer une visite.")
            return redirect('patient_detail', pk=self.traitement.patient_id)
        if self.traitement.statut != StatutTraitement.EN_COURS:
            messages.error(request, "Ce traitement est clôturé : aucune visite ne peut être ajoutée.")
            return redirect('traitement_fiche', pk=self.traitement.patient_id)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'patients'
        context['patient'] = self.traitement.patient
        context['traitement'] = self.traitement
        return context

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

    template_name = 'treatment/modifier_traitement.html'
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

    template_name = 'examens/bon_controle.html'
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


class CarteDuMaladeView(InfirmierRequiredMixin, DetailView):
    """US4.3 — Carte du malade : identité, rendez-vous, résultats simples.

    Réservée à l'infirmier (gestion des rendez-vous et carte)."""

    model = Patient
    template_name = 'appointments/carte_malade.html'
    context_object_name = 'patient'

    def dispatch(self, request, *args, **kwargs):
        patient = get_object_or_404(Patient, pk=self.kwargs['pk'])
        if patient.statut == StatutDossier.PROVISOIRE:
            messages.error(request, "Dossier provisoire : finalisez l'admission avant d'accéder à la carte du malade.")
            return redirect('patient_detail', pk=patient.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        detecter_perdus_de_vue()
        context = super().get_context_data(**kwargs)
        patient = self.object
        context['active_nav'] = 'patients'
        context['traitement'] = getattr(patient, 'traitement', None)
        context['rendez_vous'] = patient.rendez_vous.all()[:15]
        context['rdv_form'] = RendezVousForm()
        resultats = (
            ExamenPrescription.objects
            .filter(patient=patient, statut=StatutExamen.RESULTATS_DISPONIBLES)
            .select_related('medecin')
            .prefetch_related('examens')
            [:6]
        )
        context['resultats_recents'] = resultats
        return context


class RendezVousCreateView(InfirmierRequiredMixin, FormView):
    """US4.3 — Planifie un rendez-vous (agenda partagé, sans conflit).

    La carte du malade et ses rendez-vous sont édités par l'infirmier.
    """

    form_class = RendezVousForm
    http_method_names = ['post']

    def dispatch(self, request, *args, **kwargs):
        self.patient = get_object_or_404(Patient, pk=self.kwargs['pk'])
        if self.patient.statut == StatutDossier.PROVISOIRE:
            messages.error(request, "Dossier provisoire : finalisez l'admission avant de planifier un rendez-vous.")
            return redirect('patient_detail', pk=self.patient.pk)
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


class RendezVousStatutView(InfirmierRequiredMixin, View):
    """US4.3 — Marque un rendez-vous comme effectué ou annulé (infirmier)."""

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


class TraitementCloturerView(MedecinRequiredMixin, FormView):
    """Issue finale et clôture du dossier (évaluées par le médecin)."""

    template_name = 'treatment/traitement_cloture.html'
    form_class = CloturerTraitementForm

    def dispatch(self, request, *args, **kwargs):
        self.traitement = get_object_or_404(Traitement, patient_id=self.kwargs['pk'])
        if self.traitement.statut != StatutTraitement.EN_COURS:
            messages.info(self.request, "Ce dossier est déjà clôturé.")
            return redirect('traitement_fiche', pk=self.traitement.patient_id)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'patients'
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