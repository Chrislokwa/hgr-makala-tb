from django.contrib import admin

from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('ndp', 'full_name', 'sexe', 'date_naissance', 'statut', 'cree_par', 'cree_le')
    list_filter = ('statut',)
    search_fields = ('ndp', 'nom', 'post_nom', 'prenom', 'telephone')
    readonly_fields = ('ndp', 'cree_le')
    fieldsets = (
        (None, {'fields': ('ndp', 'nom', 'post_nom', 'prenom', 'sexe', 'date_naissance', 'statut')}),
        ('Adresse', {'fields': ('district', 'secteur', 'cellule', 'village', 'telephone')}),
        ('Évaluation clinique initiale', {'fields': (
            'poids',
            'signe_toux_persistante', 'signe_fievre_sueurs', 'signe_perte_poids',
            'signe_hemoptysie', 'signe_contact_cas_tpm',
            'comorb_vih', 'comorb_diabete', 'comorb_malnutrition', 'comorb_autre',
            'autres_comorbidites', 'observations_cliniques',
        )}),
        ('Traçabilité', {'fields': ('cree_le', 'cree_par')}),
    )