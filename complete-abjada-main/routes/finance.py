"""Financial management: received payments, AR, liabilities, expenses, customer profiles."""
from datetime import datetime, date
from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, or_, and_, cast, String
from extensions import db
from models import Order, Payment, Customer, Liability, Expense, User, Transaction

# Financial sections on /accounts are driven only by Transaction.account_type
AT_RECEIVED = 'Account received'
AT_RECEIVABLE = 'Receivable'
AT_LIABILITY = 'Liability'
from role_helpers import is_super_admin_role


def _account_type_eq(col, canonical_label):
    """Match account_type case-insensitively (handles stray spaces in legacy rows)."""
    return func.lower(func.trim(col)) == (canonical_label or '').strip().lower()
from finance_logic import validate_order_amounts

finance_bp = Blueprint('finance', __name__)


def _paginate(q, default_per=25):
    page = request.args.get('page', 1, type=int)
    per = request.args.get('per_page', default_per, type=int)
    per = min(per, 200)
    return q.paginate(page=page, per_page=per, error_out=False)


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], '%Y-%m-%d').date()
    except Exception:
        return None


def _admin_required():
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    if not is_super_admin_role(claims.get('role')):
        return jsonify({'error': 'Admin access required'}), 403
    return None


@finance_bp.route('/summary', methods=['GET'])
@jwt_required()
def finance_summary():
    err = _admin_required()
    if err:
        return err

    # All three buckets come from the Transaction form (account_type routing)
    total_received = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        _account_type_eq(Transaction.account_type, AT_RECEIVED)
    ).scalar() or 0.0

    total_receivable = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        _account_type_eq(Transaction.account_type, AT_RECEIVABLE)
    ).scalar() or 0.0

    total_liabilities = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        _account_type_eq(Transaction.account_type, AT_LIABILITY)
    ).scalar() or 0.0

    # Expenses
    total_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).scalar() or 0.0

    net_balance = float(total_received) - float(total_expenses) - float(total_liabilities)

    return jsonify({
        'total_received': round(float(total_received), 2),
        'total_receivable': round(float(total_receivable), 2),
        'total_liabilities': round(float(total_liabilities), 2),
        'total_expenses': round(float(total_expenses), 2),
        'net_balance': round(net_balance, 2),
        'currency': 'KES',
    })


@finance_bp.route('/received-payments', methods=['GET'])
@jwt_required()
def received_payments_report():
    err = _admin_required()
    if err:
        return err
    df = _parse_date(request.args.get('date_from'))
    dt = _parse_date(request.args.get('date_to'))
    search = (request.args.get('search') or '').strip().lower()
    q = Transaction.query.filter(_account_type_eq(Transaction.account_type, AT_RECEIVED))
    eff = func.date(func.coalesce(Transaction.transaction_date, Transaction.created_at))
    if df:
        q = q.filter(eff >= df)
    if dt:
        q = q.filter(eff <= dt)
    if search:
        like = '%' + search + '%'
        q = q.filter(or_(
            Transaction.details.ilike(like),
            Transaction.counterparty.ilike(like),
        ))
    q = q.order_by(func.coalesce(Transaction.transaction_date, Transaction.created_at).desc())
    pag = _paginate(q)
    items = []
    for t in pag.items:
        items.append({
            'id': t.id,
            'amount': float(t.amount or 0),
            'method': t.method,
            'transaction_date': t.transaction_date.isoformat() if t.transaction_date else None,
            'created_at': t.created_at.isoformat() if t.created_at else None,
            'counterparty': (t.counterparty or '').strip() or None,
            'customer_id': getattr(t, 'customer_id', None),
            'details': t.details,
            'currency': t.currency,
        })
    return jsonify({
        'items': items,
        'total': pag.total,
        'pages': pag.pages,
        'page': pag.page,
    })


@finance_bp.route('/receivable', methods=['GET'])
@jwt_required()
def receivable_report():
    err = _admin_required()
    if err:
        return err
    search = (request.args.get('search') or '').strip().lower()
    q = Transaction.query.filter(_account_type_eq(Transaction.account_type, AT_RECEIVABLE))
    if search:
        like = '%' + search + '%'
        q = q.filter(or_(
            Transaction.counterparty.ilike(like),
            Transaction.details.ilike(like),
        ))
    q = q.order_by(func.coalesce(Transaction.transaction_date, Transaction.created_at).desc())
    pag = _paginate(q, default_per=100)
    rows = []
    for t in pag.items:
        amt = float(t.amount or 0)
        pa_raw = getattr(t, 'paid_amount', None)
        pa_f = float(pa_raw) if pa_raw is not None else 0.0
        rows.append({
            'id': t.id,
            'amount': amt,
            'paid_amount': round(pa_f, 2) if pa_raw is not None else None,
            'balance_due': round(max(0.0, amt - pa_f), 2),
            'method': (getattr(t, 'method', None) or 'cash'),
            'transaction_date': t.transaction_date.isoformat() if t.transaction_date else None,
            'customer_name': (t.counterparty or '').strip() or '—',
            'payment_status': getattr(t, 'payment_status', None) or 'unpaid',
            'details': t.details,
        })
    return jsonify({'items': rows, 'total': pag.total, 'pages': pag.pages, 'page': pag.page})


@finance_bp.route('/liabilities', methods=['GET'])
@jwt_required()
def list_liabilities():
    err = _admin_required()
    if err:
        return err
    q = Transaction.query.filter(_account_type_eq(Transaction.account_type, AT_LIABILITY)).order_by(
        func.coalesce(Transaction.transaction_date, Transaction.created_at).desc()
    )
    search = (request.args.get('search') or '').strip()
    if search:
        like = '%' + search + '%'
        q = q.filter(or_(
            Transaction.counterparty.ilike(like),
            Transaction.details.ilike(like),
        ))
    pag = _paginate(q)
    items = []
    for t in pag.items:
        ps = (getattr(t, 'payment_status', None) or 'unpaid').lower()
        items.append({
            'id': t.id,
            'amount': float(t.amount or 0),
            'creditor_name': (t.counterparty or '').strip() or '—',
            'transaction_date': t.transaction_date.isoformat() if t.transaction_date else None,
            'status': ps,
            'details': t.details,
        })
    return jsonify({
        'items': items,
        'total': pag.total,
        'pages': pag.pages,
        'page': pag.page,
    })


@finance_bp.route('/liabilities', methods=['POST'])
@jwt_required()
def create_liability():
    err = _admin_required()
    if err:
        return err
    data = request.get_json() or {}
    name = (data.get('creditor_name') or '').strip()
    amt = data.get('amount')
    if not name or amt is None:
        return jsonify({'error': 'creditor_name and amount required'}), 400
    try:
        amt = float(amt)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid amount'}), 400
    if amt <= 0:
        return jsonify({'error': 'amount must be positive'}), 400
    ld = data.get('liability_date')
    liability_date = None
    if ld:
        liability_date = _parse_date(str(ld))
    L = Liability(
        creditor_name=name,
        phone=(data.get('phone') or '').strip() or None,
        amount=amt,
        paid_amount=float(data.get('paid_amount') or 0),
        liability_date=liability_date,
        description=(data.get('description') or '').strip() or None,
        created_by=get_jwt_identity(),
    )
    ok, msg = validate_order_amounts(L.amount, L.paid_amount)
    if not ok:
        return jsonify({'error': msg}), 400
    if L.paid_amount > L.amount + 1e-6:
        return jsonify({'error': 'paid_amount cannot exceed amount'}), 400
    db.session.add(L)
    db.session.commit()
    return jsonify(L.to_dict()), 201


@finance_bp.route('/liabilities/<int:lid>', methods=['PUT'])
@jwt_required()
def update_liability(lid):
    err = _admin_required()
    if err:
        return err
    L = Liability.query.get(lid)
    if not L:
        return jsonify({'error': 'Not found'}), 404
    data = request.get_json() or {}
    if 'creditor_name' in data:
        L.creditor_name = (data.get('creditor_name') or '').strip() or L.creditor_name
    if 'phone' in data:
        L.phone = (data.get('phone') or '').strip() or None
    if 'amount' in data:
        try:
            L.amount = float(data.get('amount'))
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid amount'}), 400
    if 'paid_amount' in data:
        try:
            L.paid_amount = float(data.get('paid_amount') or 0)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid paid_amount'}), 400
    if 'description' in data:
        L.description = (data.get('description') or '').strip() or None
    if 'liability_date' in data:
        ld = data.get('liability_date')
        L.liability_date = _parse_date(str(ld)) if ld else None
    if L.paid_amount > L.amount + 1e-6:
        return jsonify({'error': 'paid_amount cannot exceed amount'}), 400
    db.session.commit()
    return jsonify(L.to_dict())


@finance_bp.route('/liabilities/<int:lid>', methods=['DELETE'])
@jwt_required()
def delete_liability(lid):
    err = _admin_required()
    if err:
        return err
    L = Liability.query.get(lid)
    if not L:
        return jsonify({'error': 'Not found'}), 404
    db.session.delete(L)
    db.session.commit()
    return jsonify({'ok': True})


@finance_bp.route('/liabilities/<int:lid>/pay', methods=['POST'])
@jwt_required()
def pay_liability(lid):
    """Record a payment toward a liability (reduces balance)."""
    err = _admin_required()
    if err:
        return err
    L = Liability.query.get(lid)
    if not L:
        return jsonify({'error': 'Not found'}), 404
    data = request.get_json() or {}
    try:
        pay = float(data.get('amount') or 0)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid amount'}), 400
    if pay <= 0:
        return jsonify({'error': 'amount must be positive'}), 400
    L.paid_amount = float(L.paid_amount or 0) + pay
    if L.paid_amount > L.amount + 1e-6:
        L.paid_amount = L.amount
    db.session.commit()
    return jsonify(L.to_dict())


@finance_bp.route('/expenses', methods=['GET'])
@jwt_required()
def list_expenses():
    err = _admin_required()
    if err:
        return err
    q = Expense.query.order_by(Expense.created_at.desc())
    df = _parse_date(request.args.get('date_from'))
    dt = _parse_date(request.args.get('date_to'))
    cat = (request.args.get('category') or '').strip()
    if df:
        q = q.filter(and_(Expense.expense_date.isnot(None), Expense.expense_date >= df))
    if dt:
        q = q.filter(and_(Expense.expense_date.isnot(None), Expense.expense_date <= dt))
    if cat:
        q = q.filter(Expense.category.ilike('%' + cat + '%'))
    pag = _paginate(q)
    return jsonify({
        'items': [x.to_dict() for x in pag.items],
        'total': pag.total,
        'pages': pag.pages,
        'page': pag.page,
    })


@finance_bp.route('/expenses', methods=['POST'])
@jwt_required()
def create_expense():
    err = _admin_required()
    if err:
        return err
    data = request.get_json() or {}
    category = (data.get('category') or '').strip()
    amt = data.get('amount')
    if not category or amt is None:
        return jsonify({'error': 'category and amount required'}), 400
    try:
        amt = float(amt)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid amount'}), 400
    if amt <= 0:
        return jsonify({'error': 'amount must be positive'}), 400
    ed = data.get('expense_date')
    expense_date = _parse_date(str(ed)) if ed else date.today()
    e = Expense(
        category=category,
        amount=amt,
        expense_date=expense_date,
        description=(data.get('description') or '').strip() or None,
        created_by=get_jwt_identity(),
    )
    db.session.add(e)
    db.session.commit()
    return jsonify(e.to_dict()), 201


@finance_bp.route('/expenses/<int:eid>', methods=['PUT'])
@jwt_required()
def update_expense(eid):
    err = _admin_required()
    if err:
        return err
    e = Expense.query.get(eid)
    if not e:
        return jsonify({'error': 'Not found'}), 404
    data = request.get_json() or {}
    if 'category' in data:
        e.category = (data.get('category') or '').strip() or e.category
    if 'amount' in data:
        try:
            e.amount = float(data.get('amount'))
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid amount'}), 400
    if 'description' in data:
        e.description = (data.get('description') or '').strip() or None
    if 'expense_date' in data:
        ed = data.get('expense_date')
        e.expense_date = _parse_date(str(ed)) if ed else None
    db.session.commit()
    return jsonify(e.to_dict())


@finance_bp.route('/expenses/<int:eid>', methods=['DELETE'])
@jwt_required()
def delete_expense(eid):
    err = _admin_required()
    if err:
        return err
    e = Expense.query.get(eid)
    if not e:
        return jsonify({'error': 'Not found'}), 404
    db.session.delete(e)
    db.session.commit()
    return jsonify({'ok': True})


@finance_bp.route('/customers/<int:cid>/profile', methods=['GET'])
@jwt_required()
def customer_financial_profile(cid):
    err = _admin_required()
    if err:
        return err
    c = Customer.query.get(cid)
    if not c:
        return jsonify({'error': 'Customer not found'}), 404
    orders = list(c.orders.all())
    total_orders = len(orders)
    total_order_value = sum(float(o.total_price or 0) for o in orders)
    total_paid = sum(float(o.advance_paid or 0) for o in orders)
    remaining = max(0, round(total_order_value - total_paid, 2))
    payment_history = []
    for o in orders:
        for p in o.payments.order_by(Payment.created_at.desc()).all():
            payment_history.append({
                'id': p.id,
                'order_id': o.id,
                'amount': p.amount,
                'notes': p.notes,
                'created_at': p.created_at.isoformat() if p.created_at else None,
            })
    payment_history.sort(key=lambda x: x.get('created_at') or '', reverse=True)
    return jsonify({
        'customer': c.to_dict(),
        'total_orders': total_orders,
        'total_order_value': round(total_order_value, 2),
        'total_paid': round(total_paid, 2),
        'remaining_balance': remaining,
        'payment_history': payment_history,
    })


# --- PDF reports & transaction documents (ReportLab) ---


def _transaction_to_pdf_dict(t):
    d = t.to_dict()
    try:
        if getattr(t, 'customer_id', None):
            c = Customer.query.get(t.customer_id)
            if c and (c.full_name or '').strip():
                d['counterparty'] = (d.get('counterparty') or '').strip() or c.full_name
    except Exception:
        pass
    return d


@finance_bp.route('/transactions/<int:tid>/pdf', methods=['GET'])
@jwt_required()
def transaction_document_pdf(tid):
    err = _admin_required()
    if err:
        return err
    t = Transaction.query.get(tid)
    if not t:
        return jsonify({'error': 'Transaction not found'}), 404
    from utils.finance_pdf import (
        pdf_transaction_receipt,
        pdf_transaction_invoice,
        pdf_transaction_liability,
    )
    kind = (request.args.get('kind') or '').strip().lower()
    at = (t.account_type or '').strip().lower()
    if not kind:
        if at == 'account received':
            kind = 'receipt'
        elif at == 'receivable':
            kind = 'invoice'
        elif at == 'liability':
            kind = 'liability'
        else:
            kind = 'receipt'
    d = _transaction_to_pdf_dict(t)
    if kind == 'receipt':
        buf = pdf_transaction_receipt(d)
        fname = f'receipt_tx_{tid}.pdf'
    elif kind == 'invoice':
        buf = pdf_transaction_invoice(d)
        fname = f'invoice_tx_{tid}.pdf'
    elif kind in ('liability', 'statement'):
        buf = pdf_transaction_liability(d)
        fname = f'liability_tx_{tid}.pdf'
    else:
        return jsonify({'error': 'Invalid kind; use receipt, invoice, or liability'}), 400
    dl = request.args.get('download') == '1'
    return send_file(buf, mimetype='application/pdf', as_attachment=dl, download_name=fname)


@finance_bp.route('/reports/received.pdf', methods=['GET'])
@jwt_required()
def received_payments_pdf():
    err = _admin_required()
    if err:
        return err
    from utils.finance_pdf import pdf_received_report
    df = _parse_date(request.args.get('date_from'))
    dt = _parse_date(request.args.get('date_to'))
    q = Transaction.query.filter(_account_type_eq(Transaction.account_type, AT_RECEIVED))
    eff = func.date(func.coalesce(Transaction.transaction_date, Transaction.created_at))
    if df:
        q = q.filter(eff >= df)
    if dt:
        q = q.filter(eff <= dt)
    q = q.order_by(func.coalesce(Transaction.transaction_date, Transaction.created_at).desc())
    items = q.limit(500).all()
    rows = []
    for t in items:
        rows.append({
            'amount': float(t.amount or 0),
            'method': t.method,
            'transaction_date': t.transaction_date.isoformat() if t.transaction_date else None,
            'created_at': t.created_at.isoformat() if t.created_at else None,
            'counterparty': (t.counterparty or '').strip() or None,
            'details': t.details,
            'currency': t.currency,
        })
    buf = pdf_received_report(rows, str(df) if df else None, str(dt) if dt else None)
    dl = request.args.get('download') == '1'
    return send_file(buf, mimetype='application/pdf', as_attachment=dl, download_name='received_payments_report.pdf')


@finance_bp.route('/reports/receivable.pdf', methods=['GET'])
@jwt_required()
def receivable_report_pdf():
    err = _admin_required()
    if err:
        return err
    from utils.finance_pdf import pdf_receivable_report
    q = Transaction.query.filter(_account_type_eq(Transaction.account_type, AT_RECEIVABLE))
    q = q.order_by(func.coalesce(Transaction.transaction_date, Transaction.created_at).desc())
    items = q.limit(500).all()
    rows = []
    for t in items:
        amt = float(t.amount or 0)
        pa_raw = getattr(t, 'paid_amount', None)
        pa_f = float(pa_raw) if pa_raw is not None else 0.0
        rows.append({
            'amount': amt,
            'paid_amount': round(pa_f, 2) if pa_raw is not None else None,
            'balance_due': round(max(0.0, amt - pa_f), 2),
            'method': getattr(t, 'method', None) or 'cash',
            'transaction_date': t.transaction_date.isoformat() if t.transaction_date else None,
            'customer_name': (t.counterparty or '').strip() or '—',
            'payment_status': getattr(t, 'payment_status', None) or 'unpaid',
        })
    buf = pdf_receivable_report(rows)
    dl = request.args.get('download') == '1'
    return send_file(buf, mimetype='application/pdf', as_attachment=dl, download_name='accounts_receivable_report.pdf')


@finance_bp.route('/reports/liabilities.pdf', methods=['GET'])
@jwt_required()
def liabilities_report_pdf():
    err = _admin_required()
    if err:
        return err
    from utils.finance_pdf import pdf_liabilities_report
    q = Transaction.query.filter(_account_type_eq(Transaction.account_type, AT_LIABILITY)).order_by(
        func.coalesce(Transaction.transaction_date, Transaction.created_at).desc()
    )
    items = q.limit(500).all()
    rows = []
    for t in items:
        ps = (getattr(t, 'payment_status', None) or 'unpaid').lower()
        rows.append({
            'amount': float(t.amount or 0),
            'creditor_name': (t.counterparty or '').strip() or '—',
            'transaction_date': t.transaction_date.isoformat() if t.transaction_date else None,
            'status': ps,
            'details': t.details,
        })
    buf = pdf_liabilities_report(rows)
    dl = request.args.get('download') == '1'
    return send_file(buf, mimetype='application/pdf', as_attachment=dl, download_name='liabilities_report.pdf')


@finance_bp.route('/reports/expenses.pdf', methods=['GET'])
@jwt_required()
def expenses_report_pdf():
    err = _admin_required()
    if err:
        return err
    from utils.finance_pdf import pdf_expenses_report
    q = Expense.query.order_by(Expense.created_at.desc())
    df = _parse_date(request.args.get('date_from'))
    dt = _parse_date(request.args.get('date_to'))
    cat = (request.args.get('category') or '').strip()
    if df:
        q = q.filter(and_(Expense.expense_date.isnot(None), Expense.expense_date >= df))
    if dt:
        q = q.filter(and_(Expense.expense_date.isnot(None), Expense.expense_date <= dt))
    if cat:
        q = q.filter(Expense.category.ilike('%' + cat + '%'))
    items = q.limit(500).all()
    rows = [x.to_dict() for x in items]
    buf = pdf_expenses_report(rows, str(df) if df else None, str(dt) if dt else None)
    dl = request.args.get('download') == '1'
    return send_file(buf, mimetype='application/pdf', as_attachment=dl, download_name='expenses_report.pdf')
