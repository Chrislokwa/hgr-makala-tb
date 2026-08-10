from django.shortcuts import render, redirect
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import View, ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages

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
        # Pour les autres rôles, afficher une page d'accueil avec leur rôle
        return render(request, 'authentication/dashboard.html', {
            'user': user,
            'active_nav': 'home'
        })
