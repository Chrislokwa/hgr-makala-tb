from django.shortcuts import render, redirect
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.urls import reverse_lazy

from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserChangeForm, CustomAuthenticationForm

class CustomLoginView(LoginView):
    template_name = 'authentication/login.html'
    authentication_form = CustomAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('user_profile')

class IsAdminMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == 'ADMIN'

class UserListView(IsAdminMixin, ListView):
    model = CustomUser
    template_name = 'authentication/user_list.html'
    context_object_name = 'users'
    
    def get_queryset(self):
        return CustomUser.objects.all().order_by('-date_joined')

class UserCreateView(IsAdminMixin, CreateView):
    model = CustomUser
    form_class = CustomUserCreationForm
    template_name = 'authentication/user_form.html'
    success_url = reverse_lazy('user_list')

class UserUpdateView(IsAdminMixin, UpdateView):
    model = CustomUser
    form_class = CustomUserChangeForm
    template_name = 'authentication/user_form.html'
    success_url = reverse_lazy('user_list')

class UserProfileView(LoginRequiredMixin, DetailView):
    model = CustomUser
    template_name = 'authentication/profile.html'
    context_object_name = 'user_profile'

    def get_object(self):
        return self.request.user
