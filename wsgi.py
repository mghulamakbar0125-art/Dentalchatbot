"""
PythonAnywhere WSGI entry point.

Setup steps:
1. Upload all project files to /home/YOURUSERNAME/dental-ai/
2. In PythonAnywhere Web tab → WSGI configuration file → paste this path
3. Set your environment variables below OR use PythonAnywhere's
   "Environment variables" section in the Web tab (preferred).
4. Reload the web app.
"""

import sys
import os

# ── Point to your project folder ──────────────────────────────────────────────
# Change YOURUSERNAME to your actual PythonAnywhere username
project_home = "/home/YOURUSERNAME/dental-ai"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# ── Environment variables (only needed if NOT set in PA Web tab) ──────────────
# Recommended: set these in PythonAnywhere Web tab → "Environment variables"
# instead of hardcoding them here.
#
# os.environ.setdefault("ADMIN_PASSWORD",      "change_me")
# os.environ.setdefault("OPENROUTER_API_KEY",  "sk-or-v1-...")
# os.environ.setdefault("SENDER_EMAIL",        "yourbot@gmail.com")
# os.environ.setdefault("SENDER_PASSWORD",     "gmail_app_password")
# os.environ.setdefault("GOOGLE_SHEET_ID",     "")        # optional
# os.environ.setdefault("GOOGLE_CREDENTIALS", "")        # optional JSON string

# ── Import the FastAPI app as 'application' (required by WSGI) ────────────────
from main import app as application
