"""Fabric yard + piece deduction: product-level (legacy) or product color variant."""
from __future__ import annotations

from datetime import datetime

from extensions import db
from models import FabricUsage, Inventory, Measurement, ProductColor
from services.stock_sync import sync_product_quantity_from_colors


class FabricError(Exception):
    """Business rule violation (insufficient stock, invalid input)."""


def _effective_remaining_yards(inv: Inventory) -> float:
    if inv.remaining_yards is not None:
        return float(inv.remaining_yards)
    return float(inv.total_yards or 0)


def _set_remaining(inv: Inventory, value: float) -> None:
    inv.remaining_yards = max(0.0, round(float(value), 4))


def _set_color_remaining(pc: ProductColor, value: float) -> None:
    pc.remaining_yards = max(0.0, round(float(value), 4))


def restore_fabric_for_usage(usage: FabricUsage | None) -> None:
    """Put yards/pieces back when a measurement is edited/deleted."""
    if not usage:
        return
    if usage.product_color_id:
        pc = ProductColor.query.get(usage.product_color_id)
        if not pc:
            return
        cur = pc.effective_remaining_yards()
        cap = pc.capacity_yards
        new_rem = cur + float(usage.yards_used or 0)
        if cap > 0:
            new_rem = min(new_rem, cap)
        _set_color_remaining(pc, new_rem)
        sync_product_quantity_from_colors(usage.product_id)
        return

    inv = Inventory.query.get(usage.product_id)
    if not inv:
        return
    cur = _effective_remaining_yards(inv)
    cap = float(inv.total_yards or 0) if (inv.total_yards or 0) > 0 else None
    new_rem = cur + float(usage.yards_used or 0)
    if cap is not None:
        new_rem = min(new_rem, cap)
    _set_remaining(inv, new_rem)
    inv.quantity = (inv.quantity or 0) + float(usage.pieces_deducted or 0)
    sync_product_quantity_from_colors(usage.product_id)


def deduct_fabric(
    *,
    product_id: int,
    product_color_id: int | None,
    yards: float,
    pieces: float,
    yards_from_pieces: float,
    customer_id: int,
    measurement_id: int,
) -> FabricUsage:
    """
    Subtract fabric from a color variant (preferred) or legacy product row.
    yards_from_pieces = pieces_to_deduct * yards_per_piece when using color multi-piece logic.
    """
    total_yards = float(yards) + float(yards_from_pieces or 0)

    if total_yards < 0 or pieces < 0:
        raise FabricError('Yards and pieces must be non-negative')
    if total_yards <= 0 and pieces <= 0:
        raise FabricError('Specify fabric_yards or pieces_to_deduct')

    if product_color_id:
        pc = ProductColor.query.get(product_color_id)
        if not pc:
            raise FabricError('Color variant not found')
        if pc.product_id != product_id:
            raise FabricError('Color does not belong to this product')

        rem = pc.effective_remaining_yards()
        if total_yards > rem + 1e-9:
            raise FabricError(
                f'Not enough fabric: need {total_yards:.4f} yd but only {rem:.4f} yd available for this color'
            )
        _set_color_remaining(pc, rem - total_yards)

        u = FabricUsage(
            measurement_id=measurement_id,
            product_id=product_id,
            product_color_id=product_color_id,
            customer_id=customer_id,
            yards_used=float(total_yards),
            pieces_deducted=float(pieces),
            created_at=datetime.utcnow(),
        )
        db.session.add(u)
        sync_product_quantity_from_colors(product_id)
        return u

    inv = Inventory.query.get(product_id)
    if not inv:
        raise FabricError('Product not found')

    rem = _effective_remaining_yards(inv)
    if total_yards > rem + 1e-9:
        raise FabricError(
            f'Not enough fabric: need {total_yards} yd but only {rem:.4f} yd available'
        )

    qty = float(inv.quantity or 0)
    if pieces > qty + 1e-9:
        raise FabricError(
            f'Not enough pieces: need {pieces} but only {qty} available'
        )

    if total_yards > 0:
        _set_remaining(inv, rem - total_yards)
    if pieces > 0:
        inv.quantity = max(0.0, qty - pieces)

    u = FabricUsage(
        measurement_id=measurement_id,
        product_id=product_id,
        product_color_id=None,
        customer_id=customer_id,
        yards_used=float(total_yards),
        pieces_deducted=float(pieces),
        created_at=datetime.utcnow(),
    )
    db.session.add(u)
    return u


def delete_usage_row(usage: FabricUsage | None) -> None:
    if usage:
        db.session.delete(usage)


def sync_measurement_fabric(
    measurement: Measurement,
    *,
    old_usage: FabricUsage | None,
    product_id: int | None,
    product_color_id: int | None,
    fabric_yards: float | None,
    pieces_to_deduct: float,
):
    """
    Apply fabric rules for create/update.
    Returns (new_usage, error_dict or None).
    """
    try:
        fy = float(fabric_yards) if fabric_yards is not None else 0.0
        pc = float(pieces_to_deduct) if pieces_to_deduct else 0.0
    except (TypeError, ValueError):
        return None, {'error': 'Invalid fabric_yards or pieces_to_deduct', 'status': 400}

    if old_usage:
        restore_fabric_for_usage(old_usage)
        delete_usage_row(old_usage)
        db.session.flush()

    yards_from_pieces = 0.0
    if product_color_id and pc > 0:
        col = ProductColor.query.get(product_color_id)
        if col:
            ypp = float(col.yards_per_piece or 0)
            yards_from_pieces = pc * ypp

    total_need = fy + yards_from_pieces
    if not product_id or (total_need <= 0 and pc <= 0):
        return None, None

    try:
        u = deduct_fabric(
            product_id=product_id,
            product_color_id=product_color_id,
            yards=fy,
            pieces=pc,
            yards_from_pieces=yards_from_pieces,
            customer_id=measurement.customer_id,
            measurement_id=measurement.id,
        )
        return u, None
    except FabricError as e:
        return None, {'error': str(e), 'status': 400}
