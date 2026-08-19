from django.urls import path

from .views import (
    ExamenDetailView,
    ExamenListView,
    NotificationMarquerLuesView,
    PatientCreateView,
    PatientDetailView,
    PatientListView,
    PrescriptionExamenCreateView,
    SaisieResultatView,
)

urlpatterns = [
    path('patients/', PatientListView.as_view(), name='patient_list'),
    path('patients/create/', PatientCreateView.as_view(), name='patient_create'),
    path('patients/<int:pk>/', PatientDetailView.as_view(), name='patient_detail'),
    path('patients/<int:pk>/examens/prescrire/', PrescriptionExamenCreateView.as_view(), name='prescription_create'),
    path('examens/', ExamenListView.as_view(), name='examen_list'),
    path('examens/<int:pk>/', ExamenDetailView.as_view(), name='examen_detail'),
    path('examens/<int:pk>/resultats/', SaisieResultatView.as_view(), name='resultat_saisie'),
    path('notifications/lues/', NotificationMarquerLuesView.as_view(), name='notifications_lues'),
]