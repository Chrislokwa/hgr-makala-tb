from rest_framework import serializers
from .models import Patient, DossierTraitement, RendezVous, SuiviTherapeutique

class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = '__all__'

class DossierTraitementSerializer(serializers.ModelSerializer):
    patient_detail = PatientSerializer(source='patient', read_only=True)

    class Meta:
        model = DossierTraitement
        fields = '__all__'

class RendezVousSerializer(serializers.ModelSerializer):
    class Meta:
        model = RendezVous
        fields = '__all__'

    
class SuiviTherapeutiqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = SuiviTherapeutique
        fields = '__all__'