"""Keep product.quantity in sync with fabric color rows (pieces equivalent)."""
from __future__ import annotations

from extensions import db
from models import Inventory, ProductColor


def sync_product_quantity_from_colors(product_id: int) -> None:
    """
    When a product has color variants, quantity = sum(remaining_yards / yards_per_piece)
    per color (fractional pieces allowed). Legacy products without colors are unchanged.
    """
    inv = Inventory.query.get(product_id)
    if not inv:
        return
    colors = ProductColor.query.filter_by(product_id=product_id).all()
    if not colors:
        return
    total_equiv = 0.0
    for c in colors:
        total_equiv += float(c.remaining_pieces_equivalent())
    inv.quantity = round(total_equiv, 4)
