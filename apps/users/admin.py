from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'username_snapshot', 'action', 'description', 'target_model', 'target_id', 'ip_address')
    list_filter = ('action', 'target_model')
    search_fields = ('username_snapshot', 'description', 'target_model', 'target_id')
    readonly_fields = ('timestamp', 'user', 'username_snapshot', 'action', 'description', 'target_model', 'target_id', 'ip_address', 'extra')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)


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
