"""Utilidades de formato es-MX para el pipeline.

Replica la lógica de assets/js/format.js usando localización manual
(thousands = ',', decimal = '.', rounding = half-up).
"""
from __future__ import annotations

import math
import re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import date


MESES = {
    "ene": "enero",
    "feb": "febrero",
    "mar": "marzo",
    "abr": "abril",
    "may": "mayo",
    "jun": "junio",
    "jul": "julio",
    "ago": "agosto",
    "sep": "septiembre",
    "oct": "octubre",
    "nov": "noviembre",
    "dic": "diciembre",
}

ORD = {"1": "primer", "2": "segundo", "3": "tercer", "4": "cuarto"}

TRIM_RE = re.compile(r"^([1-4])T-(\d{2})")
MONTH_RE = re.compile(r"^([A-Za-zÁÉÍÓÚáéíóú]{3})\s*(\d{2})")


def _to_decimal(value: float | int | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _js_round(x: float) -> int:
    """Math.round(x) equivalente: floor(x + 0.5)."""
    if x is None:
        return 0
    return int(math.floor(x + 0.5))


def _group_int(num_str: str) -> str:
    """Agrupa un entero positivo con ',' cada 3 dígitos (es-MX)."""
    num_str = num_str.lstrip("0") or "0"
    if len(num_str) <= 3:
        return num_str
    out = []
    for i, ch in enumerate(reversed(num_str)):
        if i and i % 3 == 0:
            out.append(",")
        out.append(ch)
    return "".join(reversed(out))


def _to_fixed(
    value: float | int | Decimal | None,
    min_frac: int = 0,
    max_frac: int | None = None,
    group: bool = True,
) -> str:
    """Formatea un número con separadores es-MX y redondeo half-up."""
    if value is None:
        return "—"
    if max_frac is None:
        max_frac = min_frac
    d = _to_decimal(value)
    if d is None:
        return "—"

    exp = Decimal(1) if max_frac == 0 else Decimal(10) ** -max_frac
    qd = d.quantize(exp, rounding=ROUND_HALF_UP)
    if qd == 0:
        qd = qd.copy_abs()

    # Representación fija con max_frac decimales
    fixed = format(qd, f".{max_frac}f")
    sign = ""
    if fixed.startswith("-"):
        sign = "-"
        fixed = fixed[1:]

    if "." in fixed:
        int_part, frac_part = fixed.split(".")
        frac_part = frac_part.rstrip("0")
        if len(frac_part) < min_frac:
            frac_part = frac_part.ljust(min_frac, "0")
        if frac_part:
            fixed = f"{int_part}.{frac_part}"
        else:
            fixed = int_part
    else:
        int_part = fixed

    if group:
        int_part = _group_int(fixed.split(".")[0])
    else:
        int_part = fixed.split(".")[0]

    frac = ""
    if "." in fixed:
        frac = "." + fixed.split(".")[1]
    return f"{sign}{int_part}{frac}"


def _to_compact(value: float | int | Decimal | None, max_frac: int = 1) -> str:
    """toLocaleString('es-MX', {notation: 'compact', maximumFractionDigits: n})."""
    if value is None:
        return "—"
    d = _to_decimal(value)
    if d is None:
        return "—"
    absv = abs(float(d))
    if absv >= 1e15:
        scale = Decimal("1e15")
        suffix = " B"
    elif absv >= 1e12:
        scale = Decimal("1e12")
        suffix = " B"
    elif absv >= 1e9:
        scale = Decimal("1e6")
        suffix = " M"
    elif absv >= 1e6:
        scale = Decimal("1e6")
        suffix = " M"
    elif absv >= 1e3:
        scale = Decimal("1e3")
        suffix = " k"
    else:
        scale = Decimal(1)
        suffix = ""
    scaled = d / scale
    exp = Decimal(10) ** -max_frac
    qd = scaled.quantize(exp, rounding=ROUND_HALF_UP)
    if qd == 0:
        qd = qd.copy_abs()
    # compacto no agrupa la parte entera
    fixed = format(qd, f".{max_frac}f").rstrip("0").rstrip(".")
    return f"{fixed}{suffix}"


def fmt_val(v: float | int | None, fmt: str) -> str:
    """fmtVal equivalente."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    if fmt in ("num", "usd"):
        return _to_fixed(_js_round(v), 0, 0)
    if fmt == "bill":
        return _to_fixed(v / 1e6, 2, 2) + " billones de pesos de 2018"
    if fmt == "idx":
        return _to_fixed(v, 1, 1)
    if fmt == "fx":
        return "$" + _to_fixed(v, 2, 2)
    if fmt == "pct-frac":
        return _to_fixed(v * 100, 1, 1) + "%"
    if fmt == "pct-raw":
        return _to_fixed(v, 1, 1) + "%"
    return str(v)


def tick(v: float | int | None, kind: str) -> str:
    """tick equivalente."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    if kind == "pct":
        return _to_fixed(_js_round(v * 10) / 10, 0, 1) + "%"
    if kind == "idx":
        return _to_fixed(_js_round(v * 10) / 10, 0, 1)
    if kind == "compact":
        return _to_compact(v, 1)
    return _to_fixed(_js_round(v), 0, 0)


def is_trim(p: str | None) -> bool:
    return bool(p and TRIM_RE.match(p))


def per_long(p: str | None) -> str:
    if not p:
        return ""
    q = TRIM_RE.match(p)
    if q:
        return f"{ORD[q.group(1)]} trimestre de 20{q.group(2)}"
    mo = MONTH_RE.match(p)
    if mo:
        m = MESES.get(mo.group(1).lower())
        if m:
            return f"{m} de 20{mo.group(2)}"
    return p


def en_frase(p: str | None) -> str:
    return ("el " if is_trim(p) else "") + per_long(p)


def resp_frase(p: str | None) -> str:
    return ("al " if is_trim(p) else "a ") + per_long(p)


def period_to_date(p: str | None) -> date | None:
    if not p:
        return None
    q = TRIM_RE.match(p)
    if q:
        month = (int(q.group(1)) - 1) * 3
        return date(2000 + int(q.group(2)), month + 1, 1)
    mo = MONTH_RE.match(p)
    if mo:
        key = mo.group(1).lower()
        if key in MESES:
            month = list(MESES.keys()).index(key)
            return date(2000 + int(mo.group(2)), month + 1, 1)
    return None
