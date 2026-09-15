from django.urls import path
from .views import CohorteView, ConsultationsDashboardView, DashboardView, ExportConsultationsExcelView, ExportConsultationsPdfView, ExportExcelView, ExportPdfView, TableauBordView

urlpatterns = [
    path('statistiques/tableau-de-bord/', TableauBordView.as_view(), name='statistics_tableau_bord'),
    path('statistiques/', DashboardView.as_view(), name='statistics_dashboard'),
    path('statistiques/resultats-traitement/', CohorteView.as_view(), name='statistics_cohorte'),
    path('statistiques/consultations/', ConsultationsDashboardView.as_view(), name='statistics_consultations'),
    path('statistiques/consultations/export/excel/', ExportConsultationsExcelView.as_view(), name='statistics_consultations_export_excel'),
    path('statistiques/consultations/export/pdf/', ExportConsultationsPdfView.as_view(), name='statistics_consultations_export_pdf'),
    path('statistiques/export/<str:rapport>/excel/', ExportExcelView.as_view(), name='statistics_export_excel'),
    path('statistiques/export/<str:rapport>/pdf/', ExportPdfView.as_view(), name='statistics_export_pdf'),
]
