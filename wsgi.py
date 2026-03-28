"""
WSGI entry for production (e.g. gunicorn 'wsgi:app').
Run from this directory (the folder that contains app.py).
"""
import os
import sys

# Ensure imports resolve when cwd is not this folder
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

from app import app as application

# Common alias
app = application
