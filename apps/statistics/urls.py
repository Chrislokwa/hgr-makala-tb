from django.urls import path
from .views import DashboardView, ExportExcelView, ExportPdfView

urlpatterns = [
    path('statistiques/', DashboardView.as_view(), name='statistics_dashboard'),
    path('statistiques/export/<str:rapport>/excel/', ExportExcelView.as_view(), name='statistics_export_excel'),
    path('statistiques/export/<str:rapport>/pdf/', ExportPdfView.as_view(), name='statistics_export_pdf'),
]
