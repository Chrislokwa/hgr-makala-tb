from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'post_nom', 'last_name', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Informations HGR Makala', {'fields': ('role', 'post_nom', 'phone')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Informations HGR Makala', {'fields': ('role', 'post_nom', 'phone')}),
    )
