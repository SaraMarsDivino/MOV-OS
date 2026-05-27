from __future__ import annotations

from pathlib import Path
import socket
from urllib.parse import urlparse

from django.conf import settings


def vite_manifest_path() -> Path:
    # Vite build writes into BASE_DIR/static/pos-cashier/.vite/manifest.json
    base_dir = getattr(settings, 'BASE_DIR', None)
    base_dir_path = base_dir if isinstance(base_dir, Path) else Path(str(base_dir))
    return base_dir_path / 'static' / 'pos-cashier' / '.vite' / 'manifest.json'


def vite_dev_server_is_up(url: str) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return False
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except Exception:
        return False


def vite_dev_server_url_if_up() -> str | None:
    url = getattr(settings, 'VITE_DEV_SERVER_URL', 'http://localhost:5173')
    return url if vite_dev_server_is_up(url) else None


def vite_build_available() -> bool:
    try:
        return vite_manifest_path().exists()
    except Exception:
        return False


def react_ui_enabled() -> bool:
    # Force React UI everywhere; legacy templates are disabled.
    return True
