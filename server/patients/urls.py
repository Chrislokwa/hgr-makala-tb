from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PatientViewSet, DossierTraitementViewSet, RendezVousViewSet, SuiviTherapeutiqueViewSet


router = DefaultRouter()
router.register(r'patients', PatientViewSet, basename='patient')
router.register(r'dossiers', DossierTraitementViewSet, basename='dossier')
router.register(r'rendezvous', RendezVousViewSet, basename='rendezvous')
router.register(r'suivis', SuiviTherapeutiqueViewSet, basename='suivi')

urlpatterns = [
    path('', include(router.urls)),
]