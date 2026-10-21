"""WSGI entry point.

Development:  flask --app wsgi run --port 5000
Production:   gunicorn --bind 0.0.0.0:5000 --workers 3 wsgi:app
"""

import os

from dotenv import load_dotenv

load_dotenv()

from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402

from app import create_app  # noqa: E402

app = create_app()

# Behind a reverse proxy (nginx, a load balancer), trust its X-Forwarded-* headers
# so request.remote_addr is the real client IP (used by rate limits and audit logs).
# Set ASZDA_TRUSTED_PROXIES to the number of proxies in front of the app.
_proxies = int(os.environ.get("ASZDA_TRUSTED_PROXIES", "0"))
if _proxies:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=_proxies, x_proto=_proxies, x_host=_proxies)
