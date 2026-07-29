from django.urls import path
from .views import (
    ExamenListView, ExamenPrescritsListView, ExamenDetailView, 
    ExamenCreateView, ExamenUpdateView, EnregistrerResultatView
)

urlpatterns = [
    path('', ExamenListView.as_view(), name='examen_list'),
    path('prescrits/', ExamenPrescritsListView.as_view(), name='examen_prescrits'),
    path('<int:pk>/', ExamenDetailView.as_view(), name='examen_detail'),
    path('create/', ExamenCreateView.as_view(), name='examen_create'),
    path('<int:pk>/edit/', ExamenUpdateView.as_view(), name='examen_edit'),
    path('<int:pk>/resultats/', EnregistrerResultatView.as_view(), name='examen_resultats'),
]