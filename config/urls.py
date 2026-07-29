from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.authentication.urls')),
    path('api/', include('apps.patients.urls')),  # <--- Inclure les routes de l'application patients
    path('api/laboratoire/', include('apps.laboratoire.urls')),
    path('api/stats/', include('apps.stats.urls')),
]

