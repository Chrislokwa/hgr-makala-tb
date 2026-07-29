from django import forms
from .models import Patient, DossierTraitement, RendezVous, SuiviTherapeutique, ExamenLaboratoire

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'w-full px-4 py-2 border rounded-lg focus:ring focus:ring-blue-300'})

class DossierTraitementForm(forms.ModelForm):
    class Meta:
        model = DossierTraitement
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'w-full px-4 py-2 border rounded-lg focus:ring focus:ring-blue-300'})

class RendezVousForm(forms.ModelForm):
    class Meta:
        model = RendezVous
        fields = '__all__'
        widgets = {
            'date_rendez_vous': forms.DateTimeInput(attrs={'type': 'datetime-local'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'w-full px-4 py-2 border rounded-lg focus:ring focus:ring-blue-300'})

class SuiviTherapeutiqueForm(forms.ModelForm):
    class Meta:
        model = SuiviTherapeutique
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'w-full px-4 py-2 border rounded-lg focus:ring focus:ring-blue-300'})

class EvaluationTraitementForm(forms.Form):
    ISSUE_CHOICES = [
        ('GUERI', 'Guéri'),
        ('TERMINE', 'Traitement terminé'),
        ('ECHEC', 'Échec du traitement'),
        ('DECEDE', 'Décédé'),
        ('PERDU', 'Perdu de vue'),
    ]
    issue_traitement = forms.ChoiceField(choices=ISSUE_CHOICES, widget=forms.Select(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}))
    remarques_medecin = forms.CharField(widget=forms.Textarea(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}), required=False)
