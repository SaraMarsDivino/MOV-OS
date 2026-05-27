from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()


def _manifest_path() -> str:
    # Vite build output directory (see frontend/pos-cashier/vite.config.ts)
    base_dir = getattr(settings, 'BASE_DIR', None)
    base_dir_path = base_dir if isinstance(base_dir, Path) else Path(str(base_dir))
    return str(base_dir_path / 'static' / 'pos-cashier' / '.vite' / 'manifest.json')


_manifest_cache: dict[str, Any] = {
    'mtime': None,
    'data': None,
}


def _load_manifest() -> Dict[str, Any]:
    path = _manifest_path()
    try:
        mtime = Path(path).stat().st_mtime
    except Exception:
        mtime = None

    cached = _manifest_cache.get('data')
    if cached is not None and _manifest_cache.get('mtime') == mtime:
        return cached

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    _manifest_cache['mtime'] = mtime
    _manifest_cache['data'] = data
    return data


def _safe_manifest() -> Dict[str, Any]:
    try:
        return _load_manifest()
    except Exception:
        return {}


def _as_list(value: Any) -> list:
    if not value:
        return []
    if isinstance(value, list):
        return value
    return []


def _collect_css(manifest: Dict[str, Any], key: str, seen: set[str] | None = None) -> list[str]:
    """Collect CSS files for a manifest entry, including imported chunks."""

    if seen is None:
        seen = set()
    if key in seen:
        return []
    seen.add(key)

    entry = manifest.get(key) or {}
    css_files: list[str] = []

    for css in _as_list(entry.get('css')):
        if isinstance(css, str):
            css_files.append(css)

    for imp in _as_list(entry.get('imports')):
        if isinstance(imp, str):
            css_files.extend(_collect_css(manifest, imp, seen=seen))

    return css_files


@register.simple_tag
def vite_build_assets(entrypoint: str) -> Optional[Dict[str, Any]]:
    """Return built asset URLs for a given Vite entrypoint.

    Usage:
      {% vite_build_assets 'src/movos-pages.tsx' as assets %}
      {% if assets %}
        <script type="module" src="{{ assets.js }}"></script>
      {% endif %}
    """

    manifest = _safe_manifest()
    if not manifest:
        return None

    entry = manifest.get(entrypoint)
    if not entry and entrypoint == 'src/movos-pages.tsx':
        # In case the manifest key uses the rollup input name.
        entry = manifest.get('movos-pages')
    if not entry and entrypoint == 'src/main.tsx':
        # In case the manifest key uses the rollup input name.
        entry = manifest.get('pos-cashier')

    if not entry:
        return None

    file_rel = entry.get('file')
    if not file_rel:
        return None

    css_rel = _collect_css(manifest, entrypoint)
    if entrypoint == 'src/movos-pages.tsx' and not css_rel:
        # In case the manifest key uses the rollup input name.
        css_rel = _collect_css(manifest, 'movos-pages')
    if entrypoint == 'src/main.tsx' and not css_rel:
        css_rel = _collect_css(manifest, 'pos-cashier')

    js_url = static(f"pos-cashier/{file_rel}")
    css_urls = []
    seen_css = set()
    for c in css_rel:
        if c in seen_css:
            continue
        seen_css.add(c)
        css_urls.append(static(f"pos-cashier/{c}"))

    return {
        'js': js_url,
        'css': css_urls,
    }
