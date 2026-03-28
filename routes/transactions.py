from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, case
from extensions import db
from models import Transaction

transactions_bp = Blueprint('transactions', __name__)


@transactions_bp.route('/summary', methods=['GET'])
@jwt_required()
def transaction_summary():
    """Balance summary by currency from all transactions. IN adds, OUT subtracts. Group by method (cash/digital)."""
    signed = case(
        (Transaction.transaction_type == 'in', Transaction.amount),
        (Transaction.transaction_type == 'out', -Transaction.amount),
        else_=0
    )
    rows = db.session.query(
        Transaction.currency,
        Transaction.method,
        func.sum(signed).label('balance')
    ).group_by(Transaction.currency, Transaction.method).all()

    # First transaction date per currency
    first_dates = db.session.query(
        Transaction.currency,
        func.min(Transaction.transaction_date).label('first_date')
    ).group_by(Transaction.currency).all()
    first_by_currency = {r.currency: r.first_date for r in first_dates}

    summary = {}
    for r in rows:
        currency = (r.currency or 'KES').upper()
        if currency not in summary:
            summary[currency] = {'digital_balance': 0, 'cash_balance': 0, 'total_balance': 0, 'first_date': first_by_currency.get(currency)}
        bal = float(r.balance or 0)
        if (r.method or 'cash').lower() == 'digital':
            summary[currency]['digital_balance'] = bal
        else:
            summary[currency]['cash_balance'] = bal
    for cur in summary:
        s = summary[cur]
        s['total_balance'] = s['digital_balance'] + s['cash_balance']
        if s.get('first_date'):
            s['first_date'] = s['first_date'].strftime('%Y-%m-%d')
        else:
            s['first_date'] = None

    # Ensure USD and KES exist
    for cur in ('USD', 'KES'):
        if cur not in summary:
            summary[cur] = {'digital_balance': 0, 'cash_balance': 0, 'total_balance': 0, 'first_date': None}
    return jsonify(summary)


def _paginate(q, default_per=25):
    page = request.args.get('page', 1, type=int)
    per = request.args.get('per_page', default_per, type=int)
    per = min(per, 100)
    return q.paginate(page=page, per_page=per, error_out=False)


@transactions_bp.route('', methods=['GET'])
@jwt_required()
def list_transactions():
    """List all shop transactions (currency, category, amount, type, method, date, details)."""
    q = Transaction.query.order_by(Transaction.transaction_date.desc())
    pag = _paginate(q)
    items = [t.to_dict() for t in pag.items]
    return jsonify({
        'items': items,
        'total': pag.total,
        'pages': pag.pages,
        'page': pag.page
    })


@transactions_bp.route('', methods=['POST'])
@jwt_required()
def create_transaction():
    """Create a new transaction. Currency: KES (default) or USD. Method: cash or digital. Type: in or out."""
    data = request.get_json() or {}
    amount = data.get('amount')
    if amount is None:
        return jsonify({'error': 'amount required'}), 400
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify({'error': 'amount must be a number'}), 400
    currency = (data.get('currency') or 'KES').upper()
    if currency not in ('KES', 'USD'):
        currency = 'KES'
    method = (data.get('method') or 'cash').lower()
    if method not in ('cash', 'digital'):
        method = 'cash'
    trans_type = (data.get('transaction_type') or 'in').lower()
    if trans_type not in ('in', 'out'):
        trans_type = 'in'
    transaction_date = data.get('transaction_date')  # optional; backend will use now if missing
    from datetime import datetime
    if transaction_date:
        try:
            s = str(transaction_date).strip()
            if 'T' in s:
                transaction_date = datetime.fromisoformat(s.replace('Z', '+00:00')[:19])
            elif len(s) >= 19:
                transaction_date = datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S')
            else:
                transaction_date = datetime.strptime(s[:10], '%Y-%m-%d')
        except Exception:
            transaction_date = None
    if not transaction_date:
        transaction_date = datetime.utcnow()
    t = Transaction(
        currency=currency,
        category=data.get('category'),
        amount=amount,
        transaction_type=trans_type,
        method=method,
        transaction_date=transaction_date,
        details=data.get('details'),
        created_by=get_jwt_identity()
    )
    db.session.add(t)
    db.session.commit()
    return jsonify(t.to_dict()), 201
