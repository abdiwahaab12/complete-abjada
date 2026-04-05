"""Parse and validate per-part fabric yard breakdown (body, sleeve, collar, ...)."""
from __future__ import annotations

import json
from typing import Any, Optional, Tuple

# Max difference allowed between stated fabric_yards and sum(breakdown)
YARD_MATCH_EPSILON = 0.02


def normalize_yard_breakdown(raw: Any) -> Tuple[Optional[dict], Optional[str]]:
    """
    Returns (dict part_key -> yards float, error message or None).
    Keys are normalized: lowercased, spaces -> underscores.
    """
    if raw is None:
        return None, None
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return None, None
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None, 'yard_breakdown must be valid JSON'
    if not isinstance(raw, dict):
        return None, 'yard_breakdown must be an object mapping part name to yards'
    out: dict[str, float] = {}
    for k, v in raw.items():
        key = str(k).strip().lower().replace(' ', '_').replace('-', '_')
        if not key:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            return None, f'Invalid yard value for part "{k}"'
        if fv < 0:
            return None, f'Negative yards not allowed for "{k}"'
        out[key] = round(fv, 4)
    return (out if out else None), None


def total_from_breakdown(bd: Optional[dict]) -> float:
    if not bd:
        return 0.0
    return round(sum(bd.values()), 4)


def breakdown_to_json(bd: Optional[dict]) -> Optional[str]:
    if not bd:
        return None
    return json.dumps(bd, sort_keys=True)


def resolve_fabric_totals(
    fabric_yards: Any,
    yard_breakdown: Any,
) -> Tuple[Optional[float], Optional[str], Optional[str], Optional[str]]:
    """
    Returns (fabric_yards_float, breakdown_json_string, error, warning).
    If yard_breakdown is provided, total yards = sum(parts); fabric_yards must match or be omitted.
    """
    bd, err = normalize_yard_breakdown(yard_breakdown)
    if err:
        return None, None, err, None

    fy_val: Optional[float] = None
    if fabric_yards is not None and str(fabric_yards).strip() != '':
        try:
            fy_val = float(fabric_yards)
        except (TypeError, ValueError):
            return None, None, 'fabric_yards must be a number', None

    if bd:
        total = total_from_breakdown(bd)
        if fy_val is not None and abs(fy_val - total) > YARD_MATCH_EPSILON:
            return (
                None,
                None,
                f'Total yards ({fy_val}) must equal the sum of yard_breakdown ({total})',
                None,
            )
        return total, breakdown_to_json(bd), None, None

    return fy_val, None, None, None
