from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from apps.patients.models import ExamenLaboratoire
from .forms import ExamenLaboratoireForm, ResultatExamenForm

class IsLaborantinMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.role == 'LABORANTIN'

class ExamenListView(LoginRequiredMixin, ListView):
    model = ExamenLaboratoire
    template_name = 'laboratoire/examen_list.html'
    context_object_name = 'examens'
    
    def get_queryset(self):
        return super().get_queryset().order_by('-date_prescription')

class ExamenPrescritsListView(LoginRequiredMixin, ListView):
    model = ExamenLaboratoire
    template_name = 'laboratoire/examen_prescrits.html'
    context_object_name = 'examens'
    
    def get_queryset(self):
        return ExamenLaboratoire.objects.filter(statut__in=['PRESCRIT', 'EN_COURS']).order_by('date_prescription')

class ExamenDetailView(LoginRequiredMixin, DetailView):
    model = ExamenLaboratoire
    template_name = 'laboratoire/examen_detail.html'
    context_object_name = 'examen'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['resultat_form'] = ResultatExamenForm(instance=self.object)
        return context

class ExamenCreateView(LoginRequiredMixin, CreateView):
    model = ExamenLaboratoire
    form_class = ExamenLaboratoireForm
    template_name = 'laboratoire/examen_form.html'
    success_url = reverse_lazy('examen_list')

class ExamenUpdateView(LoginRequiredMixin, UpdateView):
    model = ExamenLaboratoire
    form_class = ExamenLaboratoireForm
    template_name = 'laboratoire/examen_form.html'
    success_url = reverse_lazy('examen_list')

class EnregistrerResultatView(LoginRequiredMixin, IsLaborantinMixin, View):
    def post(self, request, pk):
        examen = get_object_or_404(ExamenLaboratoire, pk=pk)
        form = ResultatExamenForm(request.POST, instance=examen)
        if form.is_valid():
            examen = form.save(commit=False)
            examen.statut = 'REALISE'
            examen.realise_par = request.user
            examen.date_analyse = timezone.now()
            examen.save()
        return redirect('examen_detail', pk=pk)