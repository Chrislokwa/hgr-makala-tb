from rest_framework import serializers
from .models import (
    Patient, 
    DossierTraitement, 
    RendezVous, 
    SuiviTherapeutique, 
    ExamenLaboratoire  # <--- Cet import manquait !
)

class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = '__all__'


class DossierTraitementSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    categorie_display = serializers.CharField(source='get_categorie_display', read_only=True)
    patient_nom = serializers.CharField(source='patient.nom', read_only=True)
    patient_prenom = serializers.CharField(source='patient.prenom', read_only=True)

    class Meta:
        model = DossierTraitement
        fields = '__all__'


class RendezVousSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)

    class Meta:
        model = RendezVous
        fields = '__all__'


class SuiviTherapeutiqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = SuiviTherapeutique
        fields = '__all__'


class ExamenLaboratoireSerializer(serializers.ModelSerializer):
    type_examen_display = serializers.CharField(source='get_type_examen_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)

    class Meta:
        model = ExamenLaboratoire
        fields = '__all__'