from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import UserProfileView

urlpatterns = [
    # Route pour se connecter (renvoie access & refresh tokens)
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    
    # Route pour rafraîchir un token expiré
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Route pour obtenir son propre profil
    path('me/', UserProfileView.as_view(), name='user_profile'),
]