from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # On inclut les routes sous le préfixe /api/auth/
    path('api/auth/', include('authentication.urls')),
]