from __future__ import annotations

from decimal import Decimal
from typing import Any

from django import template

from MOVOS.money import to_clp_pesos

register = template.Library()


@register.filter(name='clp')
def clp(value: Any) -> str:
    """Format any numeric value as whole CLP pesos with thousands separator '.' and no decimals.

    Examples:
    - 54990.00 -> '54.990'
    - Decimal('100000') -> '100.000'
    - None / '' -> '0'
    """
    if value is None:
        return '0'

    if isinstance(value, str) and value.strip() == '':
        return '0'

    try:
        pesos = to_clp_pesos(value)
        return '{:,.0f}'.format(int(pesos)).replace(',', '.')
    except Exception:
        # As a last resort, keep the original string representation.
        try:
            return str(value)
        except Exception:
            return ''
