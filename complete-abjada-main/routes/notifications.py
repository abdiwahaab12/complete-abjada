"""Low stock alert notifications API (piece count + fabric yards + color variants)."""
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from extensions import db
from models import (
    Inventory,
    ProductColor,
    LowStockAlertRead,
    LowStockColorAlertRead,
    LOW_STOCK_ALERT_THRESHOLD,
    LOW_FABRIC_YARDS_THRESHOLD,
)

notifications_bp = Blueprint('notifications', __name__)


def _collect_low_stock_product_ids():
    """Product IDs that should appear in low-stock notifications."""
    seen = set()
    for i in Inventory.query.filter(
        Inventory.min_stock.isnot(None),
        Inventory.quantity <= Inventory.min_stock,
    ).all():
        seen.add(i.id)
    rem_eff = func.coalesce(Inventory.remaining_yards, Inventory.total_yards)
    for i in Inventory.query.filter(Inventory.total_yards > 0, rem_eff < LOW_FABRIC_YARDS_THRESHOLD).all():
        seen.add(i.id)
    for i in Inventory.query.filter(
        Inventory.min_stock.is_(None),
        Inventory.quantity <= LOW_STOCK_ALERT_THRESHOLD,
    ).all():
        seen.add(i.id)
    return seen


def _collect_low_stock_color_ids():
    ids = set()
    for c in ProductColor.query.all():
        if c.stock_status() != 'ok':
            ids.add(c.id)
    return ids


def _effective_remaining_yards(inv):
    if inv.remaining_yards is not None:
        return float(inv.remaining_yards)
    return float(inv.total_yards or 0)


@notifications_bp.route('/low-stock', methods=['GET'])
@jwt_required()
def list_low_stock_alerts():
    user_id = get_jwt_identity()
    if not isinstance(user_id, int):
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid user'}), 400

    read_ids = {r.inventory_id for r in LowStockAlertRead.query.filter_by(user_id=user_id).all()}
    read_color_ids = {r.product_color_id for r in LowStockColorAlertRead.query.filter_by(user_id=user_id).all()}

    pids_with_color_rows = {r[0] for r in db.session.query(ProductColor.product_id).distinct().all()}

    seen_inventory = set()
    seen_color = set()
    out = []

    # Per-color fabric (most specific)
    for c in ProductColor.query.order_by(ProductColor.product_id, ProductColor.color_name).all():
        st = c.stock_status()
        if st == 'ok':
            continue
        if c.id in seen_color:
            continue
        seen_color.add(c.id)
        p = Inventory.query.get(c.product_id)
        msg = 'Not Available' if st == 'not_available' else 'Low stock warning'
        out.append({
            'id': c.id,
            'scope': 'color',
            'product_id': c.product_id,
            'product_name': p.name if p else '',
            'color_name': c.color_name,
            'quantity': None,
            'unit': None,
            'item_type': p.item_type if p else None,
            'read': c.id in read_color_ids,
            'alert_type': 'color_fabric',
            'remaining_yards': round(c.effective_remaining_yards(), 4),
            'message': msg,
        })

    # Legacy: fabric yards low on product row (no per-color split)
    rem_eff = func.coalesce(Inventory.remaining_yards, Inventory.total_yards)
    fabric_q = (
        Inventory.query.filter(Inventory.total_yards > 0, rem_eff < LOW_FABRIC_YARDS_THRESHOLD)
        .order_by(rem_eff.asc())
    )
    for i in fabric_q.all():
        if i.id in seen_inventory:
            continue
        if i.id in pids_with_color_rows:
            continue
        seen_inventory.add(i.id)
        rem = _effective_remaining_yards(i)
        out.append({
            'id': i.id,
            'scope': 'product',
            'name': i.name,
            'quantity': i.quantity,
            'unit': i.unit or 'pcs',
            'item_type': i.item_type,
            'read': i.id in read_ids,
            'alert_type': 'fabric',
            'remaining_yards': round(rem, 4),
            'message': 'Stock is running low',
        })

    for i in Inventory.query.filter(
        Inventory.min_stock.isnot(None),
        Inventory.quantity <= Inventory.min_stock,
    ).order_by(Inventory.quantity.asc()).all():
        if i.id in seen_inventory:
            continue
        seen_inventory.add(i.id)
        out.append({
            'id': i.id,
            'scope': 'product',
            'name': i.name,
            'quantity': i.quantity,
            'unit': i.unit or 'pcs',
            'item_type': i.item_type,
            'read': i.id in read_ids,
            'alert_type': 'quantity',
            'message': None,
        })

    for i in Inventory.query.filter(
        Inventory.min_stock.is_(None),
        Inventory.quantity <= LOW_STOCK_ALERT_THRESHOLD,
    ).order_by(Inventory.quantity.asc()).all():
        if i.id in seen_inventory:
            continue
        seen_inventory.add(i.id)
        out.append({
            'id': i.id,
            'scope': 'product',
            'name': i.name,
            'quantity': i.quantity,
            'unit': i.unit or 'pcs',
            'item_type': i.item_type,
            'read': i.id in read_ids,
            'alert_type': 'quantity',
            'message': None,
        })

    return jsonify({
        'alerts': out,
        'unread_count': sum(1 for a in out if not a['read']),
        'low_fabric_threshold_yards': LOW_FABRIC_YARDS_THRESHOLD,
    })


@notifications_bp.route('/low-stock/<int:inventory_id>/read', methods=['POST'])
@jwt_required()
def mark_low_stock_read(inventory_id):
    user_id = get_jwt_identity()
    if not isinstance(user_id, int):
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid user'}), 400
    inv = Inventory.query.get(inventory_id)
    if not inv:
        return jsonify({'error': 'Item not found'}), 404
    rec = LowStockAlertRead.query.filter_by(user_id=user_id, inventory_id=inventory_id).first()
    if not rec:
        rec = LowStockAlertRead(user_id=user_id, inventory_id=inventory_id)
        db.session.add(rec)
        db.session.commit()
    return jsonify({'ok': True})


@notifications_bp.route('/low-stock/color/<int:color_id>/read', methods=['POST'])
@jwt_required()
def mark_low_stock_color_read(color_id):
    user_id = get_jwt_identity()
    if not isinstance(user_id, int):
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid user'}), 400
    c = ProductColor.query.get(color_id)
    if not c:
        return jsonify({'error': 'Color not found'}), 404
    rec = LowStockColorAlertRead.query.filter_by(user_id=user_id, product_color_id=color_id).first()
    if not rec:
        rec = LowStockColorAlertRead(user_id=user_id, product_color_id=color_id)
        db.session.add(rec)
        db.session.commit()
    return jsonify({'ok': True})


@notifications_bp.route('/low-stock/read-all', methods=['POST'])
@jwt_required()
def mark_all_low_stock_read():
    user_id = get_jwt_identity()
    if not isinstance(user_id, int):
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid user'}), 400
    for iid in _collect_low_stock_product_ids():
        rec = LowStockAlertRead.query.filter_by(user_id=user_id, inventory_id=iid).first()
        if not rec:
            db.session.add(LowStockAlertRead(user_id=user_id, inventory_id=iid))
    for cid in _collect_low_stock_color_ids():
        rec = LowStockColorAlertRead.query.filter_by(user_id=user_id, product_color_id=cid).first()
        if not rec:
            db.session.add(LowStockColorAlertRead(user_id=user_id, product_color_id=cid))
    db.session.commit()
    return jsonify({'ok': True})
