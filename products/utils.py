import unicodedata
from django.db.models import Q

def normalize_query(text: str) -> str:
    try:
        return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    except Exception:
        return text

def build_product_search_q(query: str) -> Q:
    """Return a Q object to search products across multiple fields similar to cashier search.

    Fields considered:
    - nombre
    - producto_id (Código 1)
    - codigo_barras (preferido)
    - codigo_alternativo (Código 2)
    - descripcion
    Accent-insensitive variant for 'nombre'.
    """
    if not query:
        return Q()
    norm = normalize_query(query)
    return (
        Q(nombre__icontains=query) |
        Q(producto_id__icontains=query) |
        Q(codigo_barras__icontains=query) |
        Q(codigo_alternativo__icontains=query) |
        Q(descripcion__icontains=query) |
        Q(nombre__icontains=norm)  # fallback normalized
    )
