"""
WSGI config for asistente_virtual project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
from pathlib import Path

from django.core.wsgi import get_wsgi_application

# Ensure NLTK uses a writable data directory in serverless/read-only environments.
# Set `NLTK_DATA` to a tmp path before importing or initializing Django so any
# package-level calls to `nltk.download()` will write into a writable location.
tmp_nltk_dir = os.environ.get('NLTK_DATA', None)
if not tmp_nltk_dir:
	# prefer platform tempdir; use /tmp as a reliable writable location on many hosts
	tmp_nltk_dir = os.environ.get('TMPDIR') or '/tmp/nltk_data'
	try:
		Path(tmp_nltk_dir).mkdir(parents=True, exist_ok=True)
		os.environ['NLTK_DATA'] = tmp_nltk_dir
	except Exception:
		# If we cannot create the dir, fall back and continue; downstream errors may occur
		pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'asistente_virtual.settings')

application = get_wsgi_application()
