from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ExamenLaboratoireViewSet

router = DefaultRouter()
router.register(r'examens', ExamenLaboratoireViewSet, basename='examen')

urlpatterns = [
    path('', include(router.urls)),
]