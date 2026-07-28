from django.shortcuts import render

from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from .serializers import CustomUserSerializer

class UserProfileView(RetrieveAPIView):
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated]  # Seuls les utilisateurs connectés ont accès

    def get_object(self):
        # Récupère automatiquement l'utilisateur associé au token envoyé
        return self.request.user# Create your views here.
