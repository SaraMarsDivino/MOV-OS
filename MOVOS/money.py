from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def parse_clp_decimal(value: Any) -> Decimal:
    """Parse amounts that may come formatted as CLP.

    Supports strings like:
    - '100.000'
    - '100.000,00'
    - '100,000.00'

    Returns a Decimal *without* forcing integer rounding.
    """
    if value is None:
        raise ValueError('empty')

    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))

    raw = str(value).strip()
    if raw == '':
        raise ValueError('empty')

    raw = raw.replace(' ', '')

    has_dot = '.' in raw
    has_comma = ',' in raw

    if has_dot and has_comma:
        # Assume rightmost separator is decimal
        if raw.rfind(',') > raw.rfind('.'):
            raw = raw.replace('.', '')
            raw = raw.replace(',', '.')
        else:
            raw = raw.replace(',', '')
    elif has_comma and not has_dot:
        parts = raw.split(',')
        if len(parts[-1]) == 2:
            raw = raw.replace(',', '.')
        else:
            raw = raw.replace(',', '')
    elif has_dot and not has_comma:
        parts = raw.split('.')
        if len(parts[-1]) != 2:
            raw = raw.replace('.', '')

    return Decimal(raw)


def to_clp_pesos(value: Any) -> Decimal:
    """Normalize any amount to whole CLP pesos (integer)."""
    if value is None:
        return Decimal('0')
    if isinstance(value, Decimal):
        dec = value
    else:
        dec = Decimal(str(value))
    return dec.quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def parse_clp_pesos(value: Any) -> Decimal:
    """Parse a CLP-formatted amount and normalize to integer pesos."""
    return to_clp_pesos(parse_clp_decimal(value))
