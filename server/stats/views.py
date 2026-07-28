import csv
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions

from patients.models import Patient, DossierTraitement
from authentication.permissions import IsStatisticien

class DashboardStatsView(APIView):
    """
    Retourne les statistiques globales pour le tableau de bord (Epic 7).
    Réservé au rôle STATISTICIEN (ou ADMIN implicitement si géré ailleurs).
    """
    permission_classes = [permissions.IsAuthenticated, IsStatisticien]

    def get(self, request, format=None):
        total_patients = Patient.objects.count()
        total_dossiers = DossierTraitement.objects.count()

        # Calcul des guérisons
        guerisons = DossierTraitement.objects.filter(statut='GUERI').count()
        taux_guerison = (guerisons / total_dossiers * 100) if total_dossiers > 0 else 0.0

        # Abandons / Perdus de vue
        abandons = DossierTraitement.objects.filter(statut='PERDU').count()

        # Nouveaux cycles (Rechutes ou Reprises)
        nouveaux_cycles = DossierTraitement.objects.filter(categorie__in=['RECHUTE', 'REPRISE']).count()

        # Cas en cours
        en_cours = DossierTraitement.objects.filter(statut='EN_COURS').count()

        data = {
            "total_patients_enregistres": total_patients,
            "total_dossiers_traitement": total_dossiers,
            "guerisons": guerisons,
            "taux_guerison_pourcentage": round(taux_guerison, 2),
            "abandons_therapeutiques": abandons,
            "nouveaux_cycles": nouveaux_cycles,
            "traitements_en_cours": en_cours,
        }

        return Response(data)

class ExportReportView(APIView):
    """
    Exporte les statistiques globales au format CSV (US 7.6).
    Réservé au rôle STATISTICIEN.
    """
    permission_classes = [permissions.IsAuthenticated, IsStatisticien]

    def get(self, request, format=None):
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="rapport_statistiques.csv"'},
        )

        writer = csv.writer(response)
        writer.writerow(['Indicateur', 'Valeur'])

        total_patients = Patient.objects.count()
        total_dossiers = DossierTraitement.objects.count()
        guerisons = DossierTraitement.objects.filter(statut='GUERI').count()
        taux_guerison = (guerisons / total_dossiers * 100) if total_dossiers > 0 else 0.0
        abandons = DossierTraitement.objects.filter(statut='PERDU').count()
        nouveaux_cycles = DossierTraitement.objects.filter(categorie__in=['RECHUTE', 'REPRISE']).count()
        en_cours = DossierTraitement.objects.filter(statut='EN_COURS').count()

        writer.writerow(['Total patients enregistrés', total_patients])
        writer.writerow(['Total dossiers traitement', total_dossiers])
        writer.writerow(['Guérisons', guerisons])
        writer.writerow(['Taux de guérison (%)', round(taux_guerison, 2)])
        writer.writerow(['Abandons thérapeutiques', abandons])
        writer.writerow(['Nouveaux cycles (Rechutes/Reprises)', nouveaux_cycles])
        writer.writerow(['Traitements en cours', en_cours])

        return response

