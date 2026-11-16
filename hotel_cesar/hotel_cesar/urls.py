"""Rotas principais do projeto Hotel Cesar."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Hotel Cesar Administração"
admin.site.site_title = "Hotel Cesar Administração"
admin.site.index_title = "Painel de administração"

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("reservas.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
