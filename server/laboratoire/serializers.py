from rest_framework import serializers
from patients.models import ExamenLaboratoire
from patients.serializers import PatientSerializer


class ExamenLaboratoireSerializer(serializers.ModelSerializer):
    patient_detail = PatientSerializer(source='patient', read_only=True)

    class Meta:
        model = ExamenLaboratoire
        fields = '__all__'