"""Single Vercel entrypoint for the whole Flask app (webhook + cron + health).

``vercel.json`` rewrites every ``/api/*`` request to this function; Flask's
own routing (see ``sdevpro/webhook_app.py``) then dispatches
``/api/webhook``, ``/api/cron``, and ``/api/health`` to the right handler.
"""

from sdevpro.webhook_app import app  # noqa: F401
