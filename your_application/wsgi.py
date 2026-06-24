from __future__ import annotations

import sys
from pathlib import Path

from a2wsgi import ASGIMiddleware


GATEWAY_SERVICE_DIR = Path(__file__).resolve().parents[1] / "gateway-service"
if str(GATEWAY_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(GATEWAY_SERVICE_DIR))

from app.main import app as gateway_app  # noqa: E402


application = ASGIMiddleware(gateway_app)
