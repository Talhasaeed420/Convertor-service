import os
import sys

# Ensure project root is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import app

# WSGI Middleware to ensure PATH_INFO matches the browser request URL
# even when Vercel rewrites requests to /api/index.py
class VercelPathNormalizer:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        # Check if Vercel set rewritten destination as PATH_INFO
        path_info = environ.get("PATH_INFO", "")
        if path_info in ("/api/index.py", "/api/index", "/api"):
            original_uri = (
                environ.get("HTTP_X_FORWARDED_URI")
                or environ.get("HTTP_X_MATCHED_PATH")
                or "/"
            )
            environ["PATH_INFO"] = original_uri.split("?")[0]
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathNormalizer(app.wsgi_app)
