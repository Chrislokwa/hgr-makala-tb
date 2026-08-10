from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View, ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q
import secrets
import string

from .models import CustomUser, UserRole
from .forms import CustomAuthenticationForm, UserAdminCreateForm, UserAdminUpdateForm
from .permissions import AdminRequiredMixin

class CustomLoginView(LoginView):
    template_name = 'authentication/login.html'
    authentication_form = CustomAuthenticationForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['demo_users'] = CustomUser.objects.filter(is_active=True).order_by('username')
        return context

    def get_success_url(self):
        return reverse_lazy('dashboard')


class DashboardView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        user = request.user
        if user.role == UserRole.ADMIN:
            return redirect('user_list')
        return render(request, 'authentication/dashboard.html', {
            'user': user,
            'active_nav': 'home'
        })


class UserListView(AdminRequiredMixin, ListView):
    model = CustomUser
    template_name = 'authentication/user_list.html'
    context_object_name = 'users'
    paginate_by = 8

    def get_queryset(self):
        queryset = CustomUser.objects.all().order_by('-date_joined')
        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(username__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(email__icontains=q)
            )
        return queryset

    def get_template_names(self):
        # Requête HTMX (recherche asynchrone) : on renvoie uniquement
        # le fragment contenant les résultats, sans la page entière.
        if self.request.headers.get('HX-Request') == 'true':
            return ['authentication/user_list_results.html']
        return ['authentication/user_list.html']

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
    template_name = 'authentication/user_create.html'
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
    template_name = 'authentication/user_edit.html'
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
