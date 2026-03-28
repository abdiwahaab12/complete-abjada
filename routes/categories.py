from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from extensions import db
from models import Category, Transaction, Order

categories_bp = Blueprint('categories', __name__)

ALLOWED_TYPES = {'transaction', 'order'}


def _usage_counts(name):
    if not name:
        return 0, 0
    tx = Transaction.query.filter(Transaction.category == name).count()
    od = Order.query.filter(Order.category == name).count()
    return tx, od


@categories_bp.route('', methods=['GET'])
@jwt_required()
def list_categories():
    ctype = (request.args.get('type') or '').strip().lower()
    q = Category.query
    if ctype:
        if ctype not in ALLOWED_TYPES:
            return jsonify({'error': 'Invalid category type'}), 400
        q = q.filter(Category.type == ctype)
    rows = q.order_by(Category.name.asc()).all()
    return jsonify([c.to_dict() for c in rows])


@categories_bp.route('/<int:cid>', methods=['GET'])
@jwt_required()
def get_category(cid):
    c = Category.query.get(cid)
    if not c:
        return jsonify({'error': 'Category not found'}), 404
    tx, od = _usage_counts(c.name)
    d = c.to_dict()
    d['transaction_count'] = tx
    d['order_count'] = od
    return jsonify(d)


@categories_bp.route('', methods=['POST'])
@jwt_required()
def create_category():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Category name is required'}), 400
    exists = Category.query.filter(
        db.func.lower(Category.name) == name.lower()
    ).first()
    if exists:
        return jsonify({'error': 'A category with this name already exists'}), 409
    ctype = (data.get('type') or '').strip().lower()
    if ctype not in ALLOWED_TYPES:
        return jsonify({'error': 'Category type must be transaction or order'}), 400
    desc = (data.get('description') or '').strip() or None
    c = Category(name=name, type=ctype, description=desc)
    db.session.add(c)
    db.session.commit()
    return jsonify(c.to_dict()), 201


@categories_bp.route('/<int:cid>', methods=['PUT'])
@jwt_required()
def update_category(cid):
    c = Category.query.get(cid)
    if not c:
        return jsonify({'error': 'Category not found'}), 404
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Category name is required'}), 400
    exists = Category.query.filter(
        db.func.lower(Category.name) == name.lower(),
        Category.id != cid
    ).first()
    if exists:
        return jsonify({'error': 'A category with this name already exists'}), 409
    old_name = c.name
    c.name = name
    if 'type' in data:
        ctype = (data.get('type') or '').strip().lower()
        if ctype not in ALLOWED_TYPES:
            return jsonify({'error': 'Category type must be transaction or order'}), 400
        c.type = ctype
    if 'description' in data:
        dv = data.get('description')
        c.description = (str(dv).strip() or None) if dv is not None else c.description
    if old_name != name:
        Transaction.query.filter(Transaction.category == old_name).update(
            {'category': name}, synchronize_session=False
        )
        Order.query.filter(Order.category == old_name).update(
            {'category': name}, synchronize_session=False
        )
    db.session.commit()
    return jsonify(c.to_dict())


@categories_bp.route('/<int:cid>', methods=['DELETE'])
@jwt_required()
def delete_category(cid):
    c = Category.query.get(cid)
    if not c:
        return jsonify({'error': 'Category not found'}), 404
    tx_count, ord_count = _usage_counts(c.name)
    force = (request.args.get('force') or '').lower() in ('1', 'true', 'yes')
    if (tx_count + ord_count) > 0 and not force:
        return jsonify({
            'error': 'Category is in use',
            'message': (
                'This category is used by transactions or orders. '
                'You can delete it anyway — category will be cleared on those records.'
            ),
            'transaction_count': tx_count,
            'order_count': ord_count,
        }), 409
    Transaction.query.filter(Transaction.category == c.name).update(
        {'category': None}, synchronize_session=False
    )
    Order.query.filter(Order.category == c.name).update(
        {'category': None}, synchronize_session=False
    )
    db.session.delete(c)
    db.session.commit()
    return jsonify({'message': 'Category deleted'})
