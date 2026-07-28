from rest_framework import viewsets, permissions, status, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone

from authentication.permissions import IsMedecin, IsMedecinOrInfirmier, IsInfirmier

from .models import Patient, DossierTraitement, RendezVous, SuiviTherapeutique, ExamenLaboratoire
from .serializers import (
    PatientSerializer, 
    DossierTraitementSerializer, 
    RendezVousSerializer, 
    SuiviTherapeutiqueSerializer,
    ExamenLaboratoireSerializer
)

class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all().order_by('-created_at')
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['sexe']
    search_fields = ['code_patient', 'nom', 'postnom', 'prenom']

class DossierTraitementViewSet(viewsets.ModelViewSet):
    queryset = DossierTraitement.objects.all().order_by('-created_at')
    serializer_class = DossierTraitementSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['statut', 'categorie']
    search_fields = ['numero_tb', 'patient__nom', 'patient__prenom', 'patient__code_patient']

    @action(detail=True, methods=['post'], url_path='evaluer', permission_classes=[IsMedecin])
    def evaluer_traitement(self, request, pk=None):
        """
        Permet au médecin d'enregistrer l'évaluation finale du patient (US5.2 & US5.3).
        Exemple d'issue: GUERI, TERMINE, ECHEC, DECEDE, PERDU
        """
        dossier = self.get_object()
        issue = request.data.get('issue_traitement')
        remarques = request.data.get('remarques_medecin', '')

        if not issue:
            return Response(
                {"error": "Veuillez spécifier l'issue du traitement (GUERI, TERMINE, ECHEC, DECEDE, PERDU)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        dossier.issue_traitement = issue
        dossier.statut = issue  # Met à jour le statut du dossier
        dossier.remarques_medecin = remarques
        dossier.date_cloture = timezone.now().date()
        dossier.save()

        serializer = self.get_serializer(dossier)
        return Response({
            "message": f"Évaluation finale enregistrée avec succès. Le dossier est désormais : {dossier.get_statut_display()}.",
            "dossier": serializer.data
        }, status=status.HTTP_200_OK)

class RendezVousViewSet(viewsets.ModelViewSet):
    queryset = RendezVous.objects.all().order_by('-date_rendez_vous')
    serializer_class = RendezVousSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='retards')
    def liste_retards(self, request):
        """
        Retourne la liste des rendez-vous dépassés (date passée)
        et qui n'ont pas encore été honorés (statut toujours 'PROGRAMME').
        """
        maintenant = timezone.now()
        rdv_en_retard = RendezVous.objects.filter(
            date_rendez_vous__lt=maintenant,
            statut='PROGRAMME'
        ).order_by('date_rendez_vous')

        serializer = self.get_serializer(rdv_en_retard, many=True)
        return Response({
            "total_retards": rdv_en_retard.count(),
            "rendez_vous": serializer.data
        })

class SuiviTherapeutiqueViewSet(viewsets.ModelViewSet):
    queryset = SuiviTherapeutique.objects.all().order_by('-date_visite')
    serializer_class = SuiviTherapeutiqueSerializer
    permission_classes = [permissions.IsAuthenticated]