from django.contrib import admin

from .models import ExamenPrescription, Notification, Patient, ResultatLabo, TypeExamen


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


@admin.register(TypeExamen)
class TypeExamenAdmin(admin.ModelAdmin):
    list_display = ('code', 'libelle', 'nb_echantillons', 'exige_culture', 'actif', 'ordre')
    list_editable = ('actif', 'ordre')


@admin.register(ExamenPrescription)
class ExamenPrescriptionAdmin(admin.ModelAdmin):
    list_display = ('numero_demande', 'patient', 'nature_echantillon', 'motif', 'date_prescription', 'statut', 'medecin')
    list_filter = ('statut', 'motif', 'nature_echantillon')
    search_fields = ('numero_demande', 'patient__nom', 'patient__prenom')
    readonly_fields = ('numero_demande', 'date_prescription')


@admin.register(ResultatLabo)
class ResultatLaboAdmin(admin.ModelAdmin):
    list_display = ('prescription', 'statut', 'echantillons', 'date_lecture', 'laborantin', 'cree_le')
    list_filter = ('statut',)
    search_fields = ('prescription__numero_demande', 'prescription__patient__nom')
    readonly_fields = ('cree_le',)

    @admin.display(description='Échantillons')
    def echantillons(self, obj):
        return f"{obj.get_echantillon_1_display()}/{obj.get_echantillon_2_display()}"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('destinataire', 'message', 'lu', 'cree_le')
    list_filter = ('lu',)
    readonly_fields = ('cree_le',)