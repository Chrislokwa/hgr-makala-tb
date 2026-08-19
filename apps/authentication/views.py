from django.shortcuts import render, redirect
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View
from django.urls import reverse_lazy

from apps.patients.models import Notification
from apps.users.models import CustomUser, UserRole
from .forms import CustomAuthenticationForm

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
        context = {
            'user': user,
            'active_nav': 'home',
        }
        if user.role == UserRole.MEDECIN:
            context['notifications'] = user.notifications.all()[:5]
            context['non_lues'] = user.notifications.filter(lu=False).count()
        return render(request, 'authentication/dashboard.html', context)
