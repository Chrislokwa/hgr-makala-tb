from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from .models import Patient, DossierTraitement, RendezVous, SuiviTherapeutique
from .forms import PatientForm, DossierTraitementForm, RendezVousForm, SuiviTherapeutiqueForm, EvaluationTraitementForm

# Mixins for permissions
class IsMedecinMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.role == 'MEDECIN'

# Patient Views
class PatientListView(LoginRequiredMixin, ListView):
    model = Patient
    template_name = 'patients/patient_list.html'
    context_object_name = 'patients'
    
    def get_queryset(self):
        queryset = super().get_queryset().order_by('-created_at')
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(nom__icontains=q) | queryset.filter(prenom__icontains=q) | queryset.filter(code_patient__icontains=q)
        return queryset

class PatientDetailView(LoginRequiredMixin, DetailView):
    model = Patient
    template_name = 'patients/patient_detail.html'
    context_object_name = 'patient'

class PatientCreateView(LoginRequiredMixin, CreateView):
    model = Patient
    form_class = PatientForm
    template_name = 'patients/patient_form.html'
    success_url = reverse_lazy('patient_list')

class PatientUpdateView(LoginRequiredMixin, UpdateView):
    model = Patient
    form_class = PatientForm
    template_name = 'patients/patient_form.html'
    success_url = reverse_lazy('patient_list')

# Dossier Views
class DossierListView(LoginRequiredMixin, ListView):
    model = DossierTraitement
    template_name = 'patients/dossier_list.html'
    context_object_name = 'dossiers'
    
    def get_queryset(self):
        return super().get_queryset().order_by('-created_at')

class DossierDetailView(LoginRequiredMixin, DetailView):
    model = DossierTraitement
    template_name = 'patients/dossier_detail.html'
    context_object_name = 'dossier'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['evaluation_form'] = EvaluationTraitementForm()
        return context

class DossierCreateView(LoginRequiredMixin, CreateView):
    model = DossierTraitement
    form_class = DossierTraitementForm
    template_name = 'patients/dossier_form.html'
    success_url = reverse_lazy('dossier_list')

class DossierUpdateView(LoginRequiredMixin, UpdateView):
    model = DossierTraitement
    form_class = DossierTraitementForm
    template_name = 'patients/dossier_form.html'
    success_url = reverse_lazy('dossier_list')

class EvaluerTraitementView(LoginRequiredMixin, IsMedecinMixin, View):
    def post(self, request, pk):
        dossier = get_object_or_404(DossierTraitement, pk=pk)
        form = EvaluationTraitementForm(request.POST)
        if form.is_valid():
            dossier.issue_traitement = form.cleaned_data['issue_traitement']
            dossier.statut = form.cleaned_data['issue_traitement']
            dossier.remarques_medecin = form.cleaned_data['remarques_medecin']
            dossier.date_cloture = timezone.now().date()
            dossier.save()
        return redirect('dossier_detail', pk=pk)

# RendezVous Views
class RendezVousListView(LoginRequiredMixin, ListView):
    model = RendezVous
    template_name = 'patients/rendezvous_list.html'
    context_object_name = 'rendezvous'
    
    def get_queryset(self):
        return super().get_queryset().order_by('-date_rendez_vous')

class RetardsListView(LoginRequiredMixin, ListView):
    model = RendezVous
    template_name = 'patients/rendezvous_retards.html'
    context_object_name = 'rendezvous'
    
    def get_queryset(self):
        maintenant = timezone.now()
        return RendezVous.objects.filter(
            date_rendez_vous__lt=maintenant,
            statut='PROGRAMME'
        ).order_by('date_rendez_vous')