from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.authentication.urls')),
    path('api/', include('apps.patients.urls')),
    path('api/laboratoire/', include('apps.laboratoire.urls')),
    path('api/stats/', include('apps.stats.urls')),
]
