from django.urls import path
from .views import DashboardStatsView, ExportReportView

urlpatterns = [
    path('dashboard/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('export/', ExportReportView.as_view(), name='export-stats'),
]
