from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Q

from .models import CustomUser, UserRole
from .forms import UserAdminCreateForm, UserAdminUpdateForm
from .permissions import AdminRequiredMixin

class UserListView(AdminRequiredMixin, ListView):
    model = CustomUser
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    paginate_by = 8

    def get_queryset(self):
        queryset = CustomUser.objects.all().order_by('-date_joined')
        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(username__icontains=q) |
                Q(first_name__icontains=q) |
                Q(post_nom__icontains=q) |
                Q(last_name__icontains=q) |
                Q(email__icontains=q) |
                Q(phone__icontains=q)
            )
        return queryset

    def get_template_names(self):
        # Requête HTMX (recherche asynchrone) : on renvoie uniquement
        # le fragment contenant les résultats, sans la page entière.
        if self.request.headers.get('HX-Request') == 'true':
            return ['users/user_list_results.html']
        return ['users/user_list.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'users'
        context['q'] = self.request.GET.get('q', '').strip()
        context['role_choices'] = UserRole.choices
        context['active_admin_count'] = CustomUser.objects.filter(is_active=True, role=UserRole.ADMIN).count()
        return context


class UserCreateView(AdminRequiredMixin, CreateView):
    model = CustomUser
    form_class = UserAdminCreateForm
    template_name = 'users/user_create.html'
    success_url = reverse_lazy('user_list')

    def form_valid(self, form):
        temp_password = 'demo'  # Mot de passe temporaire par défaut
        user = form.save(commit=False)
        user.set_password(temp_password)
        user.is_active = True
        user.save()
        messages.success(self.request, f"Compte créé : {user.username} · Mot de passe temporaire : {temp_password}")
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'users'
        return context


class UserUpdateView(AdminRequiredMixin, UpdateView):
    model = CustomUser
    form_class = UserAdminUpdateForm
    template_name = 'users/user_edit.html'
    success_url = reverse_lazy('user_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Utilisateur « {self.object.display_name} » mis à jour avec succès.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'users'
        return context


class UserToggleView(AdminRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        user_to_toggle = get_object_or_404(CustomUser, pk=pk)

        # Garde-fou 1 : Ne pas désactiver son propre compte
        if user_to_toggle == request.user:
            messages.error(request, "Impossible de désactiver votre propre compte.")
            return redirect('user_list')

        # Garde-fou 2 : Ne pas désactiver le dernier administrateur actif
        if user_to_toggle.is_active and user_to_toggle.role == UserRole.ADMIN:
            active_admins = CustomUser.objects.filter(is_active=True, role=UserRole.ADMIN).count()
            if active_admins <= 1:
                messages.error(request, "Impossible de désactiver le dernier administrateur du système.")
                return redirect('user_list')

        user_to_toggle.is_active = not user_to_toggle.is_active
        user_to_toggle.save()
        status_str = "activé" if user_to_toggle.is_active else "désactivé"
        messages.success(request, f"Le compte de {user_to_toggle.display_name} a été {status_str}.")
        return redirect('user_list')


class UserSetRoleView(AdminRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        user_to_update = get_object_or_404(CustomUser, pk=pk)
        new_role = request.POST.get('role')

        if new_role not in [choice[0] for choice in UserRole.choices]:
            messages.error(request, "Rôle invalide.")
            return redirect('user_list')

        # Garde-fou : Impossible de retirer le rôle admin du dernier administrateur actif
        if user_to_update.role == UserRole.ADMIN and new_role != UserRole.ADMIN and user_to_update.is_active:
            active_admins = CustomUser.objects.filter(is_active=True, role=UserRole.ADMIN).count()
            if active_admins <= 1:
                messages.error(request, "Impossible de retirer le rôle du dernier administrateur actif.")
                return redirect('user_list')

        user_to_update.role = new_role
        user_to_update.save()
        messages.success(request, f"Rôle de {user_to_update.display_name} mis à jour : {user_to_update.get_role_display()}.")
        return redirect('user_list')
