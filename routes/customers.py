from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from extensions import db
from models import Customer

customers_bp = Blueprint('customers', __name__)

def _paginate(q, default_per=20):
    page = request.args.get('page', 1, type=int)
    per = request.args.get('per_page', default_per, type=int)
    per = min(per, 100)
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
    pag = _paginate(q.order_by(Customer.created_at.desc()))
    return jsonify({
        'items': [c.to_dict() for c in pag.items],
        'total': pag.total,
        'pages': pag.pages,
        'page': pag.page
    })

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
    db.session.commit()
    return jsonify(c.to_dict()), 201

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
