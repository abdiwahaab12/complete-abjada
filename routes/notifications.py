"""Low stock alert notifications API."""
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import Inventory, LowStockAlertRead, LOW_STOCK_ALERT_THRESHOLD

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/low-stock', methods=['GET'])
@jwt_required()
def list_low_stock_alerts():
    """Return inventory items with quantity <= threshold; include read status for current user."""
    user_id = get_jwt_identity()
    if not isinstance(user_id, int):
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid user'}), 400
    # All items at or below threshold (e.g. 5)
    items = Inventory.query.filter(Inventory.quantity <= LOW_STOCK_ALERT_THRESHOLD).order_by(Inventory.quantity.asc()).all()
    read_ids = {r.inventory_id for r in LowStockAlertRead.query.filter_by(user_id=user_id).all()}
    out = []
    for i in items:
        out.append({
            'id': i.id,
            'name': i.name,
            'quantity': i.quantity,
            'unit': i.unit or 'pcs',
            'item_type': i.item_type,
            'read': i.id in read_ids,
        })
    return jsonify({'alerts': out, 'unread_count': sum(1 for a in out if not a['read'])})


@notifications_bp.route('/low-stock/<int:inventory_id>/read', methods=['POST'])
@jwt_required()
def mark_low_stock_read(inventory_id):
    """Mark a low-stock alert as read for the current user."""
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


@notifications_bp.route('/low-stock/read-all', methods=['POST'])
@jwt_required()
def mark_all_low_stock_read():
    """Mark all current low-stock alerts as read for the current user."""
    user_id = get_jwt_identity()
    if not isinstance(user_id, int):
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid user'}), 400
    items = Inventory.query.filter(Inventory.quantity <= LOW_STOCK_ALERT_THRESHOLD).all()
    for inv in items:
        rec = LowStockAlertRead.query.filter_by(user_id=user_id, inventory_id=inv.id).first()
        if not rec:
            rec = LowStockAlertRead(user_id=user_id, inventory_id=inv.id)
            db.session.add(rec)
    db.session.commit()
    return jsonify({'ok': True})
