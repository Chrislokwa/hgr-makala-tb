from django.urls import path

from .views import PatientCreateView, PatientDetailView, PatientListView

urlpatterns = [
    path('patients/', PatientListView.as_view(), name='patient_list'),
    path('patients/create/', PatientCreateView.as_view(), name='patient_create'),
    path('patients/<int:pk>/', PatientDetailView.as_view(), name='patient_detail'),
]