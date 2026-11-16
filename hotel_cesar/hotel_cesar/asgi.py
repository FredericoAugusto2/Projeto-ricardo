"""Configuração ASGI do projeto Hotel Cesar."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hotel_cesar.settings")
application = get_asgi_application()
