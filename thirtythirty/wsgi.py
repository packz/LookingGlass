"""
WSGI config for thirtythirty project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/howto/deployment/wsgi/
"""

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "thirtythirty.settings")

# fucking electrum
from getpass import getuser
os.environ['HOME'] = '/home/%s' % getuser()

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
