from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from extensions import db
import json

from models import (
    Customer,
    FabricUsage,
    Inventory,
    LowStockAlertRead,
    Measurement,
    ProductColor,
    LOW_FABRIC_YARDS_THRESHOLD,
)

inventory_bp = Blueprint('inventory', __name__)


def _fabric_totals_for_product(product_id: int):
    rows = ProductColor.query.filter_by(product_id=product_id).all()
    if not rows:
        return None
    cap = sum(c.capacity_yards for c in rows)
    rem = sum(c.effective_remaining_yards() for c in rows)
    used = sum(c.used_yards for c in rows)
    qty_eq = sum(c.remaining_pieces_equivalent() for c in rows)
    return {
        'total_yards': round(cap, 4),
        'remaining_yards': round(rem, 4),
        'used_yards': round(used, 4),
        'quantity_pieces_equivalent': round(qty_eq, 4),
    }


def _norm(s):
    return (s or '').strip().lower()


def _duplicate_item(name, item_type, exclude_id=None):
    q = Inventory.query.filter(
        func.lower(Inventory.name) == _norm(name),
        Inventory.item_type == (item_type or 'fabric'),
    )
    if exclude_id is not None:
        q = q.filter(Inventory.id != exclude_id)
    return q.first()


@inventory_bp.route('/overview', methods=['GET'])
@jwt_required()
def inventory_fabric_overview():
    """Dashboard: fabric yards by color, legacy product rows, out-of-stock counts."""
    colors = ProductColor.query.order_by(ProductColor.product_id, ProductColor.color_name).all()
    color_rows = [c.to_dict() for c in colors]
    total_remaining_colors = sum(c.effective_remaining_yards() for c in colors)
    total_capacity_colors = sum(c.capacity_yards for c in colors)
    total_used_colors = sum(c.used_yards for c in colors)

    sub = db.session.query(ProductColor.product_id).distinct()
    pids = [r[0] for r in sub.all()]
    if pids:
        legacy = Inventory.query.filter(~Inventory.id.in_(pids)).all()
    else:
        legacy = Inventory.query.all()

    legacy_remaining = 0.0
    legacy_cap = 0.0
    for inv in legacy:
        ty = float(inv.total_yards or 0)
        rem = inv.remaining_yards
        if rem is None:
            rem = ty
        else:
            rem = float(rem)
        legacy_cap += ty
        legacy_remaining += rem

    out_of_stock_colors = sum(1 for c in colors if c.stock_status() == 'not_available')
    low_colors = sum(1 for c in colors if c.stock_status() == 'low')
    products_with_colors = db.session.query(func.count(func.distinct(ProductColor.product_id))).scalar() or 0

    return jsonify({
        'color_variants': color_rows,
        'totals': {
            'remaining_yards_colors': round(total_remaining_colors, 4),
            'capacity_yards_colors': round(total_capacity_colors, 4),
            'used_yards_colors': round(total_used_colors, 4),
            'remaining_yards_legacy_products': round(legacy_remaining, 4),
            'capacity_yards_legacy_products': round(legacy_cap, 4),
            'remaining_yards_all': round(total_remaining_colors + legacy_remaining, 4),
        },
        'counts': {
            'color_variants': len(colors),
            'products_with_color_variants': int(products_with_colors),
            'out_of_stock_colors': out_of_stock_colors,
            'low_stock_colors': low_colors,
            'low_fabric_threshold_yards': LOW_FABRIC_YARDS_THRESHOLD,
        },
    })


@inventory_bp.route('/yard-usage-report', methods=['GET'])
@jwt_required()
def yard_usage_report():
    """
    Aggregated fabric usage: yards by product, by color, and sum of per-part
    breakdown (body, sleeve, collar, …) across all measurements that stored yard_breakdown.
    """
    product_id = request.args.get('product_id', type=int)

    q = db.session.query(FabricUsage.product_id, func.sum(FabricUsage.yards_used)).group_by(
        FabricUsage.product_id
    )
    if product_id:
        q = q.filter(FabricUsage.product_id == product_id)
    yards_by_product = {int(r[0]): float(r[1] or 0) for r in q.all()}

    q2 = (
        db.session.query(FabricUsage.product_color_id, func.sum(FabricUsage.yards_used))
        .filter(FabricUsage.product_color_id.isnot(None))
        .group_by(FabricUsage.product_color_id)
    )
    if product_id:
        q2 = q2.filter(FabricUsage.product_id == product_id)
    yards_by_color = {int(r[0]): float(r[1] or 0) for r in q2.all()}

    mq = Measurement.query.filter(Measurement.fabric_yard_breakdown.isnot(None))
    if product_id:
        mq = mq.filter(Measurement.product_id == product_id)
    part_totals = {}
    for m in mq.all():
        try:
            bd = json.loads(m.fabric_yard_breakdown)
        except Exception:
            continue
        if not isinstance(bd, dict):
            continue
        for part, yds in bd.items():
            k = str(part).strip().lower().replace(' ', '_').replace('-', '_')
            if not k:
                continue
            try:
                part_totals[k] = part_totals.get(k, 0.0) + float(yds)
            except (TypeError, ValueError):
                pass
    for k in list(part_totals.keys()):
        part_totals[k] = round(part_totals[k], 4)

    return jsonify({
        'yards_used_by_product_id': yards_by_product,
        'yards_used_by_color_id': yards_by_color,
        'yard_breakdown_by_part': part_totals,
    })


def _paginate(q, default_per=50):
    page = request.args.get('page', 1, type=int)
    per = request.args.get('per_page', default_per, type=int)
    per = min(per, 500)
    return q.paginate(page=page, per_page=per, error_out=False)

@inventory_bp.route('', methods=['GET'])
@jwt_required()
def list_inventory():
    q = Inventory.query
    item_type = request.args.get('item_type')
    low_stock = request.args.get('low_stock', type=lambda x: x and x.lower() == 'true')
    search = (request.args.get('search') or '').strip()
    if item_type:
        q = q.filter(Inventory.item_type == item_type)
    if low_stock:
        q = q.filter(Inventory.min_stock.isnot(None), Inventory.quantity <= Inventory.min_stock)
    low_fabric = request.args.get('low_fabric', type=lambda x: x and x.lower() == 'true')
    if low_fabric:
        rem_eff = func.coalesce(Inventory.remaining_yards, Inventory.total_yards)
        q = q.filter(Inventory.total_yards > 0, rem_eff < LOW_FABRIC_YARDS_THRESHOLD)
    if search:
        q = q.filter(Inventory.name.ilike('%' + search + '%'))
    pag = _paginate(q.order_by(Inventory.created_at.desc(), Inventory.name))
    return jsonify({
        'items': [i.to_dict() for i in pag.items],
        'total': pag.total,
        'pages': pag.pages or 1,
        'page': pag.page,
        'per_page': pag.per_page,
    })

@inventory_bp.route('/<int:iid>/fabric-usage', methods=['GET'])
@jwt_required()
def fabric_usage_for_product(iid):
    """Yard deductions linked to this product (tailoring usage log)."""
    if not Inventory.query.get(iid):
        return jsonify({'error': 'Item not found'}), 404
    limit = request.args.get('limit', 100, type=int)
    limit = min(max(limit, 1), 500)
    q = (
        db.session.query(FabricUsage, Customer, ProductColor)
        .join(Customer, FabricUsage.customer_id == Customer.id)
        .outerjoin(ProductColor, FabricUsage.product_color_id == ProductColor.id)
        .filter(FabricUsage.product_id == iid)
        .order_by(FabricUsage.created_at.desc())
        .limit(limit)
    )
    out = []
    for u, cust, pc in q.all():
        out.append({
            'id': u.id,
            'measurement_id': u.measurement_id,
            'yards_used': float(u.yards_used or 0),
            'pieces_deducted': float(u.pieces_deducted or 0),
            'customer_name': cust.full_name,
            'customer_id': cust.id,
            'color_name': pc.color_name if pc else None,
            'product_color_id': u.product_color_id,
            'created_at': u.created_at.isoformat() if u.created_at else None,
        })
    return jsonify({'product_id': iid, 'items': out})


@inventory_bp.route('/<int:iid>', methods=['GET'])
@jwt_required()
def get_item(iid):
    i = Inventory.query.get(iid)
    if not i:
        return jsonify({'error': 'Item not found'}), 404
    d = i.to_dict()
    agg = _fabric_totals_for_product(iid)
    if agg:
        d['fabric_totals'] = agg
        d['quantity_from_colors'] = agg['quantity_pieces_equivalent']
    if request.args.get('include_colors', '').lower() in ('1', 'true', 'yes'):
        rows = (
            ProductColor.query.filter_by(product_id=iid)
            .order_by(ProductColor.color_name.asc())
            .all()
        )
        d['colors'] = [c.to_dict() for c in rows]
    return jsonify(d)

@inventory_bp.route('', methods=['POST'])
@jwt_required()
def create_item():
    data = request.get_json() or {}
    name = data.get('name')
    item_type = data.get('item_type', 'fabric')
    if not name:
        return jsonify({'error': 'name required'}), 400
    if _duplicate_item(name, item_type):
        return jsonify({'error': 'A product with this name and category already exists'}), 409
    ty = float(data.get('total_yards') or 0)
    ry = data.get('remaining_yards')
    if ry is None:
        ry = ty
    else:
        ry = float(ry)
    if ry > ty and ty >= 0:
        ry = ty
    def _pf(v):
        if v is None or v == '':
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    i = Inventory(
        item_type=item_type,
        name=name.strip(),
        quantity=float(data.get('quantity') or 0),
        unit=data.get('unit', 'pcs'),
        min_stock=data.get('min_stock'),
        notes=data.get('notes'),
        total_yards=ty,
        remaining_yards=ry,
        price=_pf(data.get('price')),
        color_category=(data.get('color_category') or '').strip() or None,
        default_yards_per_piece=_pf(data.get('default_yards_per_piece')),
    )
    db.session.add(i)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Duplicate product (database constraint)'}), 409
    return jsonify(i.to_dict()), 201

@inventory_bp.route('/<int:iid>', methods=['PUT'])
@jwt_required()
def update_item(iid):
    i = Inventory.query.get(iid)
    if not i:
        return jsonify({'error': 'Item not found'}), 404
    data = request.get_json() or {}
    new_name = data.get('name', i.name)
    new_type = data.get('item_type', i.item_type)
    if 'name' in data or 'item_type' in data:
        dup = _duplicate_item(new_name, new_type, exclude_id=iid)
        if dup:
            return jsonify({'error': 'A product with this name and category already exists'}), 409
    def _pf(v):
        if v is None or v == '':
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    for key in ('item_type', 'name', 'quantity', 'unit', 'min_stock', 'notes', 'total_yards', 'remaining_yards'):
        if key in data:
            val = data[key]
            if key == 'name' and isinstance(val, str):
                val = val.strip()
            if key in ('total_yards', 'remaining_yards') and val is not None:
                val = float(val)
            setattr(i, key, val)
    if 'price' in data:
        i.price = _pf(data.get('price'))
    if 'color_category' in data:
        v = data.get('color_category')
        i.color_category = (v or '').strip() or None
    if 'default_yards_per_piece' in data:
        i.default_yards_per_piece = _pf(data.get('default_yards_per_piece'))
    if 'total_yards' in data or 'remaining_yards' in data:
        ty = float(i.total_yards or 0)
        ry = i.remaining_yards
        if ry is None:
            ry = ty
        else:
            ry = float(ry)
        if ry > ty:
            return jsonify({'error': 'remaining_yards cannot exceed total_yards'}), 400
        i.remaining_yards = ry
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Could not save product (duplicate?)'}), 409
    return jsonify(i.to_dict())


@inventory_bp.route('/<int:iid>', methods=['DELETE'])
@jwt_required()
def delete_item(iid):
    i = Inventory.query.get(iid)
    if not i:
        return jsonify({'error': 'Item not found'}), 404
    try:
        LowStockAlertRead.query.filter_by(inventory_id=iid).delete(synchronize_session=False)
    except Exception:
        pass
    db.session.delete(i)
    db.session.commit()
    return jsonify({'ok': True, 'deleted_id': iid})

@inventory_bp.route('/<int:iid>/adjust', methods=['POST'])
@jwt_required()
def adjust_stock(iid):
    i = Inventory.query.get(iid)
    if not i:
        return jsonify({'error': 'Item not found'}), 404
    data = request.get_json() or {}
    delta = data.get('quantity', 0)
    if delta == 0:
        return jsonify(i.to_dict())
    i.quantity = (i.quantity or 0) + float(delta)
    if i.quantity < 0:
        i.quantity = 0
    db.session.commit()
    return jsonify(i.to_dict())
