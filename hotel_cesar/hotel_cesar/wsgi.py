"""Configuração WSGI do projeto Hotel Cesar."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hotel_cesar.settings")
application = get_wsgi_application()
