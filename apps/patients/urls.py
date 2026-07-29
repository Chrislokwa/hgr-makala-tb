from django.urls import path
from .views import (
    PatientListView, PatientDetailView, PatientCreateView, PatientUpdateView,
    DossierListView, DossierDetailView, DossierCreateView, DossierUpdateView,
    EvaluerTraitementView,
    RendezVousListView, RetardsListView
)

urlpatterns = [
    # Patients
    path('', PatientListView.as_view(), name='patient_list'),
    path('<int:pk>/', PatientDetailView.as_view(), name='patient_detail'),
    path('create/', PatientCreateView.as_view(), name='patient_create'),
    path('<int:pk>/edit/', PatientUpdateView.as_view(), name='patient_edit'),
    
    # Dossiers
    path('dossiers/', DossierListView.as_view(), name='dossier_list'),
    path('dossiers/<int:pk>/', DossierDetailView.as_view(), name='dossier_detail'),
    path('dossiers/create/', DossierCreateView.as_view(), name='dossier_create'),
    path('dossiers/<int:pk>/edit/', DossierUpdateView.as_view(), name='dossier_edit'),
    path('dossiers/<int:pk>/evaluer/', EvaluerTraitementView.as_view(), name='dossier_evaluer'),

    # RendezVous
    path('rendezvous/', RendezVousListView.as_view(), name='rendezvous_list'),
    path('rendezvous/retards/', RetardsListView.as_view(), name='rendezvous_retards'),
]