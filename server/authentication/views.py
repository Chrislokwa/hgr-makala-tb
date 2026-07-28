from django.shortcuts import render

from rest_framework.generics import RetrieveAPIView
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .serializers import CustomUserSerializer, UserCreateSerializer
from .permissions import IsAdmin
from .models import CustomUser

class UserProfileView(RetrieveAPIView):
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated]  # Seuls les utilisateurs connectés ont accès

    def get_object(self):
        # Récupère automatiquement l'utilisateur associé au token envoyé
        return self.request.user

class UserViewSet(viewsets.ModelViewSet):
    """
    CRUD pour la gestion des utilisateurs (US1.1, US1.2).
    Réservé aux administrateurs.
    """
    queryset = CustomUser.objects.all().order_by('-date_joined')
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return UserCreateSerializer
        return CustomUserSerializer
