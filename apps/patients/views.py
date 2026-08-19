from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import DetailView, FormView, ListView, TemplateView, View

from .forms import DossierProvisoireForm, PrescriptionExamenForm, SaisieResultatForm
from .models import (
    ExamenPrescription,
    MotifExamen,
    NatureEchantillon,
    Patient,
    ResultatLabo,
    StatutDossier,
    StatutExamen,
    StatutResultat,
    TypeExamen,
)
from .permissions import LaborantinRequiredMixin, MedecinRequiredMixin
from .services import (
    creer_dossier_provisoire,
    creer_prescription_examen,
    enregistrer_resultats,
    trouver_prescriptions_en_attente,
)


class PatientListView(MedecinRequiredMixin, ListView):
    model = Patient
    template_name = 'patients/patient_list.html'
    context_object_name = 'patients'
    paginate_by = 8

    def get_queryset(self):
        return Patient.objects.all().order_by('-cree_le')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'patients'
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


class PatientDetailView(MedecinRequiredMixin, DetailView):
    model = Patient
    template_name = 'patients/patient_detail.html'
    context_object_name = 'patient'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'patients'
        context['prescriptions'] = (
            self.object.examens_prescrits.all()
            .prefetch_related('examens')
        )
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


class ExamenListView(LaborantinRequiredMixin, TemplateView):
    template_name = 'patients/examen_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'examens'
        en_attente = (
            ExamenPrescription.objects
            .filter(statut=StatutExamen.EN_ATTENTE)
            .select_related('patient', 'medecin')
            .prefetch_related('examens')
        )
        disponibles = (
            ExamenPrescription.objects
            .filter(statut=StatutExamen.RESULTATS_DISPONIBLES)
            .select_related('patient', 'medecin')
            .prefetch_related('examens')
        )
        context['a_traiter'] = en_attente
        context['resultats_disponibles'] = disponibles
        context['nb_a_traiter'] = en_attente.count()
        context['nb_disponibles'] = disponibles.count()
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


class NotificationMarquerLuesView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        request.user.notifications.filter(lu=False).update(lu=True)
        return redirect('dashboard')