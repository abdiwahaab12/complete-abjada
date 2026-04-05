"""Color variants for products (per-color yard stock)."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from extensions import db
from models import Inventory, ProductColor, FabricUsage
from services.stock_sync import sync_product_quantity_from_colors

product_colors_bp = Blueprint('product_colors', __name__)


def _norm_color(name: str) -> str:
    return (name or '').strip()


@product_colors_bp.route('/<int:product_id>/colors', methods=['GET'])
@jwt_required()
def list_colors(product_id):
    p = Inventory.query.get(product_id)
    if not p:
        return jsonify({'error': 'Product not found'}), 404
    rows = (
        ProductColor.query.filter_by(product_id=product_id)
        .order_by(ProductColor.color_name.asc())
        .all()
    )
    return jsonify({'product_id': product_id, 'colors': [c.to_dict() for c in rows]})


@product_colors_bp.route('/<int:product_id>/colors', methods=['POST'])
@jwt_required()
def create_color(product_id):
    p = Inventory.query.get(product_id)
    if not p:
        return jsonify({'error': 'Product not found'}), 404
    data = request.get_json() or {}
    name = _norm_color(data.get('color_name') or '')
    if not name:
        return jsonify({'error': 'color_name required'}), 400

    dup = ProductColor.query.filter(
        func.lower(ProductColor.color_name) == name.lower(),
        ProductColor.product_id == product_id,
    ).first()
    if dup:
        return jsonify({'error': 'This color already exists for this product'}), 409

    pq = int(data.get('pieces_quantity') or 0)
    ypp = float(data.get('yards_per_piece') or 0)
    cap = pq * ypp
    rem = data.get('remaining_yards')
    if rem is None:
        rem = cap
    else:
        rem = float(rem)
    if rem > cap and cap > 0:
        rem = cap

    c = ProductColor(
        product_id=product_id,
        color_name=name,
        pieces_quantity=max(0, pq),
        yards_per_piece=max(0.0, ypp),
        remaining_yards=rem,
    )
    db.session.add(c)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Duplicate color'}), 409
    sync_product_quantity_from_colors(product_id)
    db.session.commit()
    return jsonify(c.to_dict()), 201


@product_colors_bp.route('/<int:product_id>/colors/<int:color_id>', methods=['GET'])
@jwt_required()
def get_color(product_id, color_id):
    c = ProductColor.query.filter_by(id=color_id, product_id=product_id).first()
    if not c:
        return jsonify({'error': 'Color not found'}), 404
    return jsonify(c.to_dict())


@product_colors_bp.route('/<int:product_id>/colors/<int:color_id>', methods=['PUT'])
@jwt_required()
def update_color(product_id, color_id):
    c = ProductColor.query.filter_by(id=color_id, product_id=product_id).first()
    if not c:
        return jsonify({'error': 'Color not found'}), 404
    data = request.get_json() or {}
    if 'color_name' in data:
        nn = _norm_color(data['color_name'])
        if nn:
            exists = (
                ProductColor.query.filter(
                    ProductColor.product_id == product_id,
                    ProductColor.id != color_id,
                    func.lower(ProductColor.color_name) == nn.lower(),
                ).first()
            )
            if exists:
                return jsonify({'error': 'Another color already uses this name'}), 409
            c.color_name = nn
    if 'pieces_quantity' in data:
        c.pieces_quantity = max(0, int(data['pieces_quantity'] or 0))
    if 'yards_per_piece' in data:
        c.yards_per_piece = max(0.0, float(data['yards_per_piece'] or 0))
    if 'remaining_yards' in data and data['remaining_yards'] is not None:
        cap = c.capacity_yards
        rem = float(data['remaining_yards'])
        if cap > 0:
            rem = min(rem, cap)
        c.remaining_yards = max(0.0, rem)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Update failed'}), 409
    sync_product_quantity_from_colors(product_id)
    db.session.commit()
    return jsonify(c.to_dict())


@product_colors_bp.route('/<int:product_id>/colors/<int:color_id>', methods=['DELETE'])
@jwt_required()
def delete_color(product_id, color_id):
    c = ProductColor.query.filter_by(id=color_id, product_id=product_id).first()
    if not c:
        return jsonify({'error': 'Color not found'}), 404
    if FabricUsage.query.filter_by(product_color_id=color_id).first():
        return jsonify({'error': 'Cannot delete: fabric has been used from this color'}), 409
    db.session.delete(c)
    db.session.commit()
    sync_product_quantity_from_colors(product_id)
    db.session.commit()
    return jsonify({'ok': True})


@product_colors_bp.route('/<int:product_id>/colors/<int:color_id>/restock', methods=['POST'])
@jwt_required()
def restock_color(product_id, color_id):
    """Add pieces and/or yards to a color variant (extends capacity and remaining)."""
    c = ProductColor.query.filter_by(id=color_id, product_id=product_id).first()
    if not c:
        return jsonify({'error': 'Color not found'}), 404
    data = request.get_json() or {}
    add_pieces = int(data.get('add_pieces') or 0)
    add_yards = float(data.get('add_yards') or 0)
    ypp = float(c.yards_per_piece or 0)

    if add_pieces > 0:
        c.pieces_quantity = (c.pieces_quantity or 0) + add_pieces
        add_yards += add_pieces * ypp

    if add_yards > 0:
        rem = c.effective_remaining_yards()
        c.remaining_yards = rem + add_yards

    db.session.commit()
    sync_product_quantity_from_colors(product_id)
    db.session.commit()
    return jsonify(c.to_dict())
