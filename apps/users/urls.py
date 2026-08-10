from django.urls import path
from .views import (
    UserListView,
    UserCreateView,
    UserUpdateView,
    UserToggleView,
    UserSetRoleView,
)

urlpatterns = [
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/create/', UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/edit/', UserUpdateView.as_view(), name='user_edit'),
    path('users/<int:pk>/toggle/', UserToggleView.as_view(), name='user_toggle'),
    path('users/<int:pk>/role/', UserSetRoleView.as_view(), name='user_set_role'),
]
