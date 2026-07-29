import csv
from django.http import HttpResponse
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from apps.patients.models import Patient, DossierTraitement

class IsStatisticienMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.role == 'STATISTICIEN'

class DashboardStatsView(LoginRequiredMixin, IsStatisticienMixin, TemplateView):
    template_name = 'stats/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total_patients = Patient.objects.count()
        total_dossiers = DossierTraitement.objects.count()
        guerisons = DossierTraitement.objects.filter(statut='GUERI').count()
        taux_guerison = (guerisons / total_dossiers * 100) if total_dossiers > 0 else 0.0
        abandons = DossierTraitement.objects.filter(statut='PERDU').count()
        nouveaux_cycles = DossierTraitement.objects.filter(categorie__in=['RECHUTE', 'REPRISE']).count()
        en_cours = DossierTraitement.objects.filter(statut='EN_COURS').count()

        context.update({
            "total_patients": total_patients,
            "total_dossiers": total_dossiers,
            "guerisons": guerisons,
            "taux_guerison": round(taux_guerison, 2),
            "abandons": abandons,
            "nouveaux_cycles": nouveaux_cycles,
            "en_cours": en_cours,
        })
        return context

class ExportReportView(LoginRequiredMixin, IsStatisticienMixin, View):
    def get(self, request, *args, **kwargs):
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
