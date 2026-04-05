import re
from datetime import datetime

from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import TransactionCategory, Transaction, User

transaction_categories_bp = Blueprint('transaction_categories', __name__)


def slugify(name: str) -> str:
    s = (name or '').strip().lower()
    try:
        import unicodedata
        t = unicodedata.normalize('NFKD', s)
        s = t.encode('ascii', 'ignore').decode('ascii')
    except Exception:
        pass
    s = re.sub(r'[^a-z0-9\s_-]', '', s)
    s = re.sub(r'[\s-]+', '_', s).strip('_')
    return s[:120] if s else 'category'


@transaction_categories_bp.route('', methods=['GET'])
@jwt_required()
def list_transaction_categories():
    page = request.args.get('page', 1, type=int) or 1
    per_raw = request.args.get('per_page', 20, type=int) or 20
    per = max(1, min(per_raw, 100))

    search = (request.args.get('search') or '').strip()
    sort = (request.args.get('sort') or 'name').lower()
    order = (request.args.get('order') or 'asc').lower()

    q = TransactionCategory.query
    if search:
        q = q.filter(TransactionCategory.name.ilike('%' + search + '%'))

    col = TransactionCategory.name if sort == 'name' else TransactionCategory.created_at
    q = q.order_by(col.desc() if order == 'desc' else col.asc())

    pag = q.paginate(page=page, per_page=per, error_out=False)
    items = []
    for c in pag.items:
        d = c.to_dict()
        # Display-friendly label for UI.
        d['allowed_users_label'] = 'All Users' if (c.allowed_users or 'all').lower() == 'all' else str(c.allowed_users)
        if c.created_by:
            u = User.query.get(c.created_by)
            d['created_by_name'] = (u.full_name or u.username) if u else None
        else:
            d['created_by_name'] = None
        items.append(d)

    resp = make_response(jsonify({
        'items': items,
        'total': pag.total,
        'page': pag.page,
        'pages': pag.pages,
        'per_page': pag.per_page
    }))
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@transaction_categories_bp.route('', methods=['POST'])
@jwt_required()
def create_transaction_category():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400

    if TransactionCategory.query.filter_by(name=name).first():
        return jsonify({'error': 'A transaction category with this name already exists'}), 400

    cat = TransactionCategory(
        name=name,
        allowed_users=(data.get('allowed_users') or 'all'),
        created_by=None  # populated below if possible
    )

    # Best-effort created_by.
    try:
        from flask_jwt_extended import get_jwt_identity
        uid = get_jwt_identity()
        cat.created_by = uid
    except Exception:
        cat.created_by = None

    db.session.add(cat)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Could not create transaction category'}), 400

    d = cat.to_dict()
    d['allowed_users_label'] = 'All Users' if (cat.allowed_users or 'all').lower() == 'all' else str(cat.allowed_users)
    return jsonify(d), 201


@transaction_categories_bp.route('/<int:cid>', methods=['PUT'])
@jwt_required()
def update_transaction_category(cid: int):
    cat = TransactionCategory.query.get(cid)
    if not cat:
        return jsonify({'error': 'Not found'}), 404

    data = request.get_json() or {}
    name = data.get('name')
    if name is None:
        return jsonify({'error': 'name required'}), 400

    name = name.strip()
    if not name:
        return jsonify({'error': 'name required'}), 400

    other = TransactionCategory.query.filter(
        TransactionCategory.name == name,
        TransactionCategory.id != cid
    ).first()
    if other:
        return jsonify({'error': 'A transaction category with this name already exists'}), 400

    cat.name = name
    if 'allowed_users' in data and data.get('allowed_users') is not None:
        cat.allowed_users = str(data.get('allowed_users')).strip() or 'all'

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Could not update transaction category'}), 400

    d = cat.to_dict()
    d['allowed_users_label'] = 'All Users' if (cat.allowed_users or 'all').lower() == 'all' else str(cat.allowed_users)
    return jsonify(d)


@transaction_categories_bp.route('/<int:cid>', methods=['DELETE'])
@jwt_required()
def delete_transaction_category(cid: int):
    cat = TransactionCategory.query.get(cid)
    if not cat:
        return jsonify({'error': 'Not found'}), 404

    # Prevent deleting categories used by existing transactions.
    used = Transaction.query.filter_by(category=cat.name).first()
    if used:
        return jsonify({'error': 'Cannot delete a category that still has transactions'}), 400

    db.session.delete(cat)
    db.session.commit()
    return jsonify({'ok': True})

