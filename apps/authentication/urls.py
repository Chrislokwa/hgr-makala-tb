from django.urls import path
from django.contrib.auth.views import LogoutView
from django.views.generic import RedirectView
from .views import CustomLoginView, DashboardView

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='login', permanent=False)),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
]