from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone

from patients.models import ExamenLaboratoire
from .serializers import ExamenLaboratoireSerializer
from authentication.permissions import IsLaborantin

class ExamenLaboratoireViewSet(viewsets.ModelViewSet):
    queryset = ExamenLaboratoire.objects.all().order_by('-date_prescription')
    serializer_class = ExamenLaboratoireSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        # Restriction sur la création / modification pour les laborantins
        if self.action in ['enregistrer_resultats']:
            return [IsLaborantin()]
        return super().get_permissions()

    @action(detail=True, methods=['post'], url_path='resultats')
    def enregistrer_resultats(self, request, pk=None):
        """
        Permet au laborantin d'enregistrer les résultats d'un examen prescrit (US4.3)
        """
        examen = self.get_object()
        
        resultat = request.data.get('resultat')
        details = request.data.get('details_resultat', '')

        if not resultat:
            return Response(
                {"error": "Le champ 'resultat' est obligatoire (POSITIF, NEGATIF, INDETERMINE)."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        examen.resultat = resultat
        examen.details_resultat = details
        examen.statut = 'REALISE'
        examen.realise_par = request.user
        examen.date_analyse = timezone.now()
        examen.save()

        serializer = self.get_serializer(examen)
        return Response({
            "message": "Résultats enregistrés avec succès.",
            "examen": serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='prescrits')
    def examens_prescrits(self, request):
        """
        Retourne la liste des examens prescrits et en cours (US4.2)
        """
        examens = ExamenLaboratoire.objects.filter(statut__in=['PRESCRIT', 'EN_COURS']).order_by('date_prescription')
        serializer = self.get_serializer(examens, many=True)
        return Response(serializer.data)