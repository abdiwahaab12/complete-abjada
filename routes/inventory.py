from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from extensions import db
from models import Inventory

inventory_bp = Blueprint('inventory', __name__)

def _paginate(q, default_per=50):
    page = request.args.get('page', 1, type=int)
    per = request.args.get('per_page', default_per, type=int)
    per = min(per, 100)
    return q.paginate(page=page, per_page=per, error_out=False)

@inventory_bp.route('', methods=['GET'])
@jwt_required()
def list_inventory():
    q = Inventory.query
    item_type = request.args.get('item_type')
    low_stock = request.args.get('low_stock', type=lambda x: x and x.lower() == 'true')
    if item_type:
        q = q.filter(Inventory.item_type == item_type)
    if low_stock:
        q = q.filter(Inventory.min_stock.isnot(None), Inventory.quantity <= Inventory.min_stock)
    pag = _paginate(q.order_by(Inventory.name))
    return jsonify({
        'items': [i.to_dict() for i in pag.items],
        'total': pag.total,
        'pages': pag.pages,
        'page': pag.page
    })

@inventory_bp.route('/<int:iid>', methods=['GET'])
@jwt_required()
def get_item(iid):
    i = Inventory.query.get(iid)
    if not i:
        return jsonify({'error': 'Item not found'}), 404
    return jsonify(i.to_dict())

@inventory_bp.route('', methods=['POST'])
@jwt_required()
def create_item():
    data = request.get_json() or {}
    name = data.get('name')
    item_type = data.get('item_type', 'fabric')
    if not name:
        return jsonify({'error': 'name required'}), 400
    i = Inventory(
        item_type=item_type,
        name=name,
        quantity=float(data.get('quantity') or 0),
        unit=data.get('unit', 'pcs'),
        min_stock=data.get('min_stock'),
        notes=data.get('notes')
    )
    db.session.add(i)
    db.session.commit()
    return jsonify(i.to_dict()), 201

@inventory_bp.route('/<int:iid>', methods=['PUT'])
@jwt_required()
def update_item(iid):
    i = Inventory.query.get(iid)
    if not i:
        return jsonify({'error': 'Item not found'}), 404
    data = request.get_json() or {}
    for key in ('item_type', 'name', 'quantity', 'unit', 'min_stock', 'notes'):
        if key in data:
            setattr(i, key, data[key])
    db.session.commit()
    return jsonify(i.to_dict())

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
