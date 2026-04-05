from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, case
from extensions import db
from models import Transaction, User, Customer

transactions_bp = Blueprint('transactions', __name__)


def _resolve_transaction_type(account_type, explicit_type=None):
    """
    Only account type drives in/out. Category is classification only.
    Account received & Receivable → in; Liability → out.
    """
    if account_type:
        a = (account_type or '').strip().lower()
        if a == 'liability':
            return 'out'
        if a in ('account received', 'receivable'):
            return 'in'
    et = (explicit_type or 'in')
    if isinstance(et, str):
        et = et.lower()
    else:
        et = 'in'
    return et if et in ('in', 'out') else 'in'


def _payment_status_allowed_for_account_type(account_type):
    a = (account_type or '').strip().lower()
    return a in ('account received', 'receivable', 'liability')


def _validate_paid_amount_row(t):
    """Enforce paid_amount rules for Received / Receivable. Clears paid_amount for other types."""
    at = (t.account_type or '').strip().lower()
    if at not in ('account received', 'receivable'):
        t.paid_amount = None
        return None
    ps = (t.payment_status or '').strip().lower() or None
    amt = float(t.amount or 0)
    pa = t.paid_amount
    if pa is not None and pa < 0:
        return 'Total paid cannot be negative'
    if ps == 'partial':
        if pa is None or float(pa) <= 0:
            return 'Total paid is required when status is Partial'
        if float(pa) > amt + 1e-6:
            return 'Total paid cannot exceed transaction amount'
    elif ps == 'paid':
        if pa is None:
            t.paid_amount = round(amt, 2)
        elif float(pa) > amt + 1e-6:
            return 'Total paid cannot exceed transaction amount'
    else:
        if pa is not None and float(pa) > amt + 1e-6:
            return 'Total paid cannot exceed transaction amount'
    return None


def _requires_customer_name(account_type):
    a = (account_type or '').strip().lower()
    return a in ('account received', 'receivable')


def _parse_customer_id(data):
    raw = data.get('customer_id')
    if raw is None or raw == '':
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _normalize_account_type(v):
    """Must be one of: Account received, Receivable, Liability (aligned with finance categories)."""
    canonical = ('Account received', 'Receivable', 'Liability')
    aliases = {
        'account received': 'Account received',
        'received': 'Account received',
        'receivable': 'Receivable',
        'liability': 'Liability',
    }
    s = (v or '').strip()
    if not s:
        return 'Account received'
    low = s.lower()
    if low in aliases:
        return aliases[low]
    for label in canonical:
        if label.lower() == low:
            return label
    # Legacy values from older builds → default
    return 'Account received'


@transactions_bp.route('/summary', methods=['GET'])
@jwt_required()
def transaction_summary():
    """Balance summary by currency. Methods: cash and mpesa (M-Pesa)."""
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

    first_dates = db.session.query(
        Transaction.currency,
        func.min(Transaction.transaction_date).label('first_date')
    ).group_by(Transaction.currency).all()
    first_by_currency = {r.currency: r.first_date for r in first_dates}

    def _bucket(method):
        m = (method or 'cash').lower().replace(' ', '_').replace('-', '')
        if m == 'cash':
            return 'cash_balance'
        # mpesa + legacy non-cash stored as M-Pesa bucket
        return 'mpesa_balance'

    summary = {}
    for r in rows:
        currency = (r.currency or 'KES').upper()
        if currency not in summary:
            summary[currency] = {
                'cash_balance': 0, 'mpesa_balance': 0,
                'mobile_balance': 0, 'bank_balance': 0, 'digital_balance': 0,
                'total_balance': 0,
                'first_date': first_by_currency.get(currency),
            }
        bal = float(r.balance or 0)
        bkey = _bucket(r.method)
        summary[currency][bkey] = summary[currency].get(bkey, 0) + bal
    for cur in summary:
        s = summary[cur]
        mp = float(s.get('mpesa_balance', 0))
        s['digital_balance'] = mp
        s['mobile_balance'] = mp
        s['bank_balance'] = 0.0
        s['total_balance'] = float(s.get('cash_balance', 0)) + mp
        if s.get('first_date'):
            s['first_date'] = s['first_date'].strftime('%Y-%m-%d')
        else:
            s['first_date'] = None

    for cur in ('USD', 'KES'):
        if cur not in summary:
            summary[cur] = {
                'cash_balance': 0, 'mpesa_balance': 0,
                'mobile_balance': 0, 'bank_balance': 0, 'digital_balance': 0,
                'total_balance': 0, 'first_date': None,
            }
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
    items = []
    for t in pag.items:
        d = t.to_dict()
        try:
            u = User.query.get(t.created_by) if getattr(t, 'created_by', None) else None
            d['created_by_name'] = (u.full_name or u.username) if u else '-'
        except Exception:
            d['created_by_name'] = '-'
        items.append(d)
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
    method = _normalize_method(data.get('method'))
    account_type = _normalize_account_type(data.get('account_type'))
    trans_type = _resolve_transaction_type(account_type, data.get('transaction_type'))
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
    ps = (data.get('payment_status') or '').strip().lower() or None
    if ps and ps not in ('paid', 'unpaid', 'partial'):
        ps = None
    if not _payment_status_allowed_for_account_type(account_type):
        ps = None
    cat = (data.get('category') or '').strip() or None
    cp = (data.get('counterparty') or '').strip() or None
    if cp and len(cp) > 200:
        cp = cp[:200]
    cid = _parse_customer_id(data)
    if cid is not None:
        cust = Customer.query.get(cid)
        if not cust:
            return jsonify({'error': 'Customer not found'}), 400
        if not cp:
            cp = (cust.full_name or '').strip() or None
            if cp and len(cp) > 200:
                cp = cp[:200]
    if _requires_customer_name(account_type):
        if not cp or not str(cp).strip():
            return jsonify({'error': 'Customer name is required for Received and Receivable transactions'}), 400
    paid_amt = None
    at_low = (account_type or '').strip().lower()
    if at_low in ('account received', 'receivable'):
        raw_pa = data.get('paid_amount')
        if raw_pa is not None and raw_pa != '':
            try:
                paid_amt = float(raw_pa)
            except (TypeError, ValueError):
                return jsonify({'error': 'Total paid must be a number'}), 400
            if paid_amt < 0:
                return jsonify({'error': 'Total paid cannot be negative'}), 400
            if paid_amt > amount + 1e-6:
                return jsonify({'error': 'Total paid cannot exceed transaction amount'}), 400
    t = Transaction(
        currency=currency,
        category=cat,
        account_type=account_type,
        counterparty=cp,
        customer_id=cid,
        amount=amount,
        paid_amount=round(paid_amt, 2) if paid_amt is not None else None,
        transaction_type=trans_type,
        method=method,
        transaction_date=transaction_date,
        details=data.get('details'),
        payment_status=ps,
        created_by=get_jwt_identity()
    )
    err_pa = _validate_paid_amount_row(t)
    if err_pa:
        return jsonify({'error': err_pa}), 400
    db.session.add(t)
    db.session.commit()
    return jsonify(t.to_dict()), 201


def _normalize_currency(v):
    v = (v or 'KES').upper()
    return v if v in ('KES', 'USD') else 'KES'


def _normalize_method(v):
    """Only cash and mpesa (M-Pesa); legacy values map to mpesa."""
    m = (v or 'cash').lower().replace(' ', '_').replace('-', '')
    if m in ('mpesa', 'mpes', 'm_pesa', 'mobile_money', 'mobilemoney', 'digital', 'bank', 'bank_transfer', 'wire'):
        return 'mpesa'
    return 'cash'


def _normalize_type(v):
    v = (v or 'in').lower()
    return v if v in ('in', 'out') else 'in'


def _parse_transaction_date(transaction_date):
    """Accept ISO datetime / HTML datetime-local / date strings."""
    from datetime import datetime
    if not transaction_date:
        return None
    try:
        s = str(transaction_date).strip()
        if 'T' in s:
            # Strip timezone if needed
            if len(s) >= 19:
                s2 = s.replace('Z', '+00:00')[:19]
                return datetime.fromisoformat(s2)
        if len(s) >= 19:
            return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S')
        return datetime.strptime(s[:10], '%Y-%m-%d')
    except Exception:
        return None


@transactions_bp.route('/<int:tid>', methods=['GET'])
@jwt_required()
def get_transaction(tid: int):
    t = Transaction.query.get(tid)
    if not t:
        return jsonify({'error': 'Transaction not found'}), 404
    d = t.to_dict()
    try:
        u = User.query.get(t.created_by) if getattr(t, 'created_by', None) else None
        d['created_by_name'] = (u.full_name or u.username) if u else '-'
    except Exception:
        d['created_by_name'] = '-'
    try:
        if getattr(t, 'customer_id', None):
            c = Customer.query.get(t.customer_id)
            if c:
                d['customer_name'] = c.full_name
    except Exception:
        pass
    return jsonify(d)


@transactions_bp.route('/<int:tid>', methods=['PUT'])
@jwt_required()
def update_transaction(tid: int):
    t = Transaction.query.get(tid)
    if not t:
        return jsonify({'error': 'Transaction not found'}), 404
    data = request.get_json() or {}

    if 'currency' in data:
        t.currency = _normalize_currency(data.get('currency'))
    if 'category' in data:
        t.category = (data.get('category') or '').strip() or None
    if 'account_type' in data:
        t.account_type = _normalize_account_type(data.get('account_type'))
    if 'amount' in data:
        try:
            t.amount = float(data.get('amount'))
        except (TypeError, ValueError):
            return jsonify({'error': 'amount must be a number'}), 400
    if 'method' in data:
        t.method = _normalize_method(data.get('method'))
    if 'details' in data:
        t.details = data.get('details')
    if 'counterparty' in data:
        cp = (data.get('counterparty') or '').strip() or None
        t.counterparty = (cp[:200] if cp else None)

    if 'customer_id' in data:
        raw = data.get('customer_id')
        if raw is None or raw == '':
            t.customer_id = None
        else:
            try:
                cid = int(raw)
            except (TypeError, ValueError):
                return jsonify({'error': 'Invalid customer_id'}), 400
            cust = Customer.query.get(cid)
            if not cust:
                return jsonify({'error': 'Customer not found'}), 400
            t.customer_id = cid
            if not (t.counterparty and str(t.counterparty).strip()):
                t.counterparty = ((cust.full_name or '').strip()[:200] or None)

    # Optional: allow updating transaction_date
    if 'transaction_date' in data:
        dt = _parse_transaction_date(data.get('transaction_date'))
        if dt:
            t.transaction_date = dt

    explicit_tt = data.get('transaction_type', t.transaction_type)
    t.transaction_type = _resolve_transaction_type(t.account_type, explicit_tt)

    if 'payment_status' in data:
        ps = (data.get('payment_status') or '').strip().lower() or None
        if ps in ('paid', 'unpaid', 'partial', ''):
            t.payment_status = ps if ps else None
    if not _payment_status_allowed_for_account_type(t.account_type):
        t.payment_status = None

    if 'paid_amount' in data:
        raw_pa = data.get('paid_amount')
        if raw_pa is None or raw_pa == '':
            t.paid_amount = None
        else:
            try:
                t.paid_amount = float(raw_pa)
            except (TypeError, ValueError):
                return jsonify({'error': 'Total paid must be a number'}), 400
            if t.paid_amount < 0:
                return jsonify({'error': 'Total paid cannot be negative'}), 400

    if _requires_customer_name(t.account_type):
        if not (t.counterparty and str(t.counterparty).strip()):
            return jsonify({'error': 'Customer name is required for Received and Receivable transactions'}), 400

    err_pa = _validate_paid_amount_row(t)
    if err_pa:
        return jsonify({'error': err_pa}), 400

    db.session.commit()

    d = t.to_dict()
    try:
        u = User.query.get(t.created_by) if getattr(t, 'created_by', None) else None
        d['created_by_name'] = (u.full_name or u.username) if u else '-'
    except Exception:
        d['created_by_name'] = '-'
    return jsonify(d)


@transactions_bp.route('/<int:tid>', methods=['DELETE'])
@jwt_required()
def delete_transaction(tid: int):
    t = Transaction.query.get(tid)
    if not t:
        return jsonify({'error': 'Transaction not found'}), 404
    db.session.delete(t)
    db.session.commit()
    return jsonify({'message': 'Transaction deleted'})
