from django import forms
from apps.patients.models import ExamenLaboratoire

class ExamenLaboratoireForm(forms.ModelForm):
    class Meta:
        model = ExamenLaboratoire
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'w-full px-4 py-2 border rounded-lg focus:ring focus:ring-blue-300'})

class ResultatExamenForm(forms.ModelForm):
    class Meta:
        model = ExamenLaboratoire
        fields = ['resultat', 'details_resultat']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'w-full px-4 py-2 border rounded-lg focus:ring focus:ring-blue-300'})
