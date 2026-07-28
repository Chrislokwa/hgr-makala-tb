from rest_framework import viewsets, permissions
from .models import Patient, DossierTraitement, RendezVous, SuiviTherapeutique
from .serializers import PatientSerializer, DossierTraitementSerializer, RendezVousSerializer, SuiviTherapeutiqueSerializer

class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all().order_by('-created_at')
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]

class DossierTraitementViewSet(viewsets.ModelViewSet):
    queryset = DossierTraitement.objects.all().order_by('-created_at')
    serializer_class = DossierTraitementSerializer
    permission_classes = [permissions.IsAuthenticated]

class RendezVousViewSet(viewsets.ModelViewSet):
    queryset = RendezVous.objects.all().order_by('-date_rendez_vous')
    serializer_class = RendezVousSerializer
    permission_classes = [permissions.IsAuthenticated]

class SuiviTherapeutiqueViewSet(viewsets.ModelViewSet):
    queryset = SuiviTherapeutique.objects.all().order_by('-date_visite')
    serializer_class = SuiviTherapeutiqueSerializer
    permission_classes = [permissions.IsAuthenticated]    