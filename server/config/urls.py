from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('authentication.urls')),
    path('api/', include('patients.urls')),  # <--- Inclure les routes de l'application patients
    path('api/laboratoire/', include('laboratoire.urls')),
    path('api/stats/', include('stats.urls')),
]

