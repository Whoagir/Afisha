import os

import django
from django.conf import settings  # noqa: F401

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "afisha.settings")
django.setup()
