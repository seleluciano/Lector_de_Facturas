"""
ASGI config for gestion_facturas project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_facturas.settings')

application = get_asgi_application() 