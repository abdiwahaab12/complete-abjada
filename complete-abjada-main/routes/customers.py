from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func
from extensions import db
from models import Customer, Measurement, Inventory, ProductColor
from services.fabric_service import sync_measurement_fabric
from services.yard_breakdown import resolve_fabric_totals

customers_bp = Blueprint('customers', __name__)

def _paginate(q, default_per=20):
    page = request.args.get('page', 1, type=int)
    per = request.args.get('per_page', default_per, type=int)
    per = min(per, 500)
    return q.paginate(page=page, per_page=per, error_out=False)

@customers_bp.route('', methods=['GET'])
@jwt_required()
def list_customers():
    q = Customer.query
    search = request.args.get('search', '').strip()
    if search:
        q = q.filter(
            Customer.full_name.ilike(f'%{search}%') |
            Customer.phone.ilike(f'%{search}%') |
            (Customer.email.isnot(None) & Customer.email.ilike(f'%{search}%'))
        )
    sort_dir = (request.args.get('sort_dir') or 'desc').lower()
    if sort_dir not in ('asc', 'desc'):
        sort_dir = 'desc'
    order_col = Customer.created_at.asc() if sort_dir == 'asc' else Customer.created_at.desc()
    pag = _paginate(q.order_by(order_col))
    ids = [c.id for c in pag.items]
    count_map = {}
    if ids:
        rows = (
            db.session.query(Measurement.customer_id, func.count(Measurement.id))
            .filter(Measurement.customer_id.in_(ids))
            .group_by(Measurement.customer_id)
            .all()
        )
        count_map = {int(r[0]): int(r[1]) for r in rows}
    items = []
    for c in pag.items:
        d = c.to_dict()
        d['has_measurements'] = count_map.get(c.id, 0) > 0
        items.append(d)
    out = {
        'items': items,
        'total': pag.total,
        'pages': pag.pages or 1,
        'page': pag.page,
        'per_page': pag.per_page,
        'sort_dir': sort_dir,
    }
    if request.args.get('include_stats'):
        tc = Customer.query.count()
        wm = (
            db.session.query(func.count(func.distinct(Measurement.customer_id)))
            .scalar()
        ) or 0
        rate = int(round(100.0 * wm / tc)) if tc else 0
        out['stats'] = {
            'total_customers': tc,
            'with_measurements': wm,
            'completion_rate': min(100, rate),
        }
    return jsonify(out)

@customers_bp.route('/<int:cid>', methods=['GET'])
@jwt_required()
def get_customer(cid):
    c = Customer.query.get(cid)
    if not c:
        return jsonify({'error': 'Customer not found'}), 404
    d = c.to_dict()
    d['measurements'] = [m.to_dict() for m in c.measurements]
    d['orders'] = [o.to_dict() for o in c.orders]
    return jsonify(d)

@customers_bp.route('', methods=['POST'])
@jwt_required()
def create_customer():
    data = request.get_json() or {}
    sub = data.get('measurement') or data.get('tailor_measurement')
    name = data.get('full_name')
    phone = data.get('phone')
    if not name or not phone:
        return jsonify({'error': 'Full name and phone required'}), 400
    c = Customer(
        full_name=name,
        phone=phone,
        email=data.get('email'),
        address=data.get('address'),
        special_notes=data.get('special_notes')
    )
    db.session.add(c)
    db.session.flush()

    if sub and isinstance(sub, dict):
        product_id = sub.get('product_id')
        product_color_id = sub.get('product_color_id')
        pc = None
        if product_color_id is not None:
            product_color_id = int(product_color_id)
            pc = ProductColor.query.get(product_color_id)
            if not pc:
                db.session.rollback()
                return jsonify({'error': 'Invalid product_color_id'}), 400
            product_id = pc.product_id
        elif product_id is not None:
            product_id = int(product_id)
            if not Inventory.query.get(product_id):
                db.session.rollback()
                return jsonify({'error': 'Invalid product_id'}), 400
        else:
            product_id = None

        def _pf(v, d=None):
            if v is None:
                return d
            try:
                return float(v)
            except (TypeError, ValueError):
                return d

        raw_bd = sub.get('yard_breakdown') or sub.get('fabric_yard_breakdown')
        fabric_yards, bd_json, res_err = resolve_fabric_totals(sub.get('fabric_yards'), raw_bd)
        if res_err:
            db.session.rollback()
            return jsonify({'error': res_err}), 400

        pieces_to_deduct = _pf(sub.get('pieces_to_deduct'), 0.0) or 0.0
        fy = float(fabric_yards) if fabric_yards is not None else 0.0
        extra_y = 0.0
        if product_color_id and pieces_to_deduct > 0 and pc:
            extra_y = pieces_to_deduct * float(pc.yards_per_piece or 0)

        if (fy + extra_y > 0 or (pieces_to_deduct > 0 and not product_color_id)) and not product_id:
            db.session.rollback()
            return jsonify({'error': 'product_id or product_color_id required for measurement stock deduction'}), 400

        m = Measurement(
            customer_id=c.id,
            profile_type=sub.get('profile_type', 'standard'),
            chest=sub.get('chest'),
            waist=sub.get('waist'),
            shoulder=sub.get('shoulder'),
            length=sub.get('length'),
            sleeve=sub.get('sleeve'),
            neck=sub.get('neck'),
            hip=sub.get('hip'),
            inseam=sub.get('inseam'),
            notes=sub.get('notes'),
            product_id=product_id,
            product_color_id=product_color_id,
            fabric_yards=fabric_yards,
            fabric_yard_breakdown=bd_json,
            clothing_type=(sub.get('clothing_type') or '').strip() or None,
        )
        db.session.add(m)
        db.session.flush()

        _, err = sync_measurement_fabric(
            m,
            old_usage=None,
            product_id=product_id,
            product_color_id=product_color_id,
            fabric_yards=fabric_yards,
            pieces_to_deduct=pieces_to_deduct,
        )
        if err:
            db.session.rollback()
            return jsonify({'error': err['error']}), err['status']

    db.session.commit()
    db.session.refresh(c)
    out = c.to_dict()
    if sub and isinstance(sub, dict):
        out['measurements'] = [x.to_dict() for x in c.measurements]
    return jsonify(out), 201

@customers_bp.route('/<int:cid>', methods=['PUT'])
@jwt_required()
def update_customer(cid):
    c = Customer.query.get(cid)
    if not c:
        return jsonify({'error': 'Customer not found'}), 404
    data = request.get_json() or {}
    if data.get('full_name') is not None:
        c.full_name = data['full_name']
    if data.get('phone') is not None:
        c.phone = data['phone']
    if 'email' in data:
        c.email = data['email']
    if 'address' in data:
        c.address = data['address']
    if 'special_notes' in data:
        c.special_notes = data['special_notes']
    db.session.commit()
    return jsonify(c.to_dict())

@customers_bp.route('/<int:cid>', methods=['DELETE'])
@jwt_required()
def delete_customer(cid):
    c = Customer.query.get(cid)
    if not c:
        return jsonify({'error': 'Customer not found'}), 404
    db.session.delete(c)
    db.session.commit()
    return jsonify({'message': 'Deleted'}), 204
