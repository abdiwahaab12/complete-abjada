from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import OperationalError
from extensions import db
from models import Bank, User

banks_bp = Blueprint('banks', __name__)


def _ensure_banks_table():
    """Create banks table if missing (e.g. after model was added)."""
    try:
        Bank.query.limit(1).first()
    except OperationalError as e:
        msg = str(e).lower()
        if 'no such table' in msg or "doesn't exist" in msg or '1146' in msg:
            db.create_all()
        else:
            raise


def _paginate(q, default_per=25):
    page = request.args.get('page', 1, type=int)
    per = request.args.get('per_page', default_per, type=int)
    per = min(per, 100)
    return q.paginate(page=page, per_page=per, error_out=False)


def _next_account_number():
    """Generate next account number like ACC-0040."""
    last = Bank.query.order_by(Bank.id.desc()).first()
    n = (last.id + 1) if last else 1
    return f'ACC-{n:04d}'


@banks_bp.route('', methods=['GET'])
@jwt_required()
def list_banks():
    _ensure_banks_table()
    q = Bank.query.order_by(Bank.created_at.desc())
    pag = _paginate(q)
    items = [b.to_dict() for b in pag.items]
    return jsonify({
        'items': items,
        'total': pag.total,
        'pages': pag.pages,
        'page': pag.page
    })


@banks_bp.route('/<int:bid>', methods=['GET'])
@jwt_required()
def get_bank(bid):
    _ensure_banks_table()
    b = Bank.query.get(bid)
    if not b:
        return jsonify({'error': 'Bank not found'}), 404
    return jsonify(b.to_dict())


@banks_bp.route('', methods=['POST'])
@jwt_required()
def create_bank():
    _ensure_banks_table()
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    account_number = (data.get('account_number') or '').strip()
    if not account_number or Bank.query.filter_by(account_number=account_number).first():
        account_number = _next_account_number()
    balance = float(data.get('balance', 0) or 0)
    user_id = data.get('user_id')
    if user_id is not None:
        user_id = int(user_id) if user_id else None
    if user_id and not User.query.get(user_id):
        user_id = None
    b = Bank(account_number=account_number, name=name, balance=balance, user_id=user_id)
    db.session.add(b)
    db.session.commit()
    return jsonify(b.to_dict()), 201


@banks_bp.route('/<int:bid>', methods=['PUT'])
@jwt_required()
def update_bank(bid):
    _ensure_banks_table()
    b = Bank.query.get(bid)
    if not b:
        return jsonify({'error': 'Bank not found'}), 404
    data = request.get_json() or {}
    if 'name' in data:
        b.name = (data['name'] or '').strip() or b.name
    if 'account_number' in data:
        bn = (data['account_number'] or '').strip()
        if bn and Bank.query.filter(Bank.account_number == bn, Bank.id != bid).first() is None:
            b.account_number = bn
    if 'balance' in data:
        try:
            b.balance = float(data['balance'])
        except (TypeError, ValueError):
            pass
    if 'user_id' in data:
        uid = data['user_id']
        b.user_id = int(uid) if uid and User.query.get(int(uid)) else None
    db.session.commit()
    return jsonify(b.to_dict())


@banks_bp.route('/<int:bid>', methods=['DELETE'])
@jwt_required()
def delete_bank(bid):
    _ensure_banks_table()
    b = Bank.query.get(bid)
    if not b:
        return jsonify({'error': 'Bank not found'}), 404
    db.session.delete(b)
    db.session.commit()
    return jsonify({'message': 'Deleted'}), 204
