from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func, or_
from extensions import db
from models import Order, Payment, Customer, Inventory, Transaction, Swap, Bank

reports_bp = Blueprint('reports', __name__)


def _parse_date(s, default=None):
    if not s:
        return default
    try:
        return datetime.strptime(str(s)[:10], '%Y-%m-%d').date()
    except ValueError:
        return default


def _paginate(q, default_per=50):
    page = request.args.get('page', 1, type=int)
    per = request.args.get('per_page', default_per, type=int)
    per = min(per, 100)
    return q.paginate(page=page, per_page=per, error_out=False)


# --- Report endpoints with date range, search, filter ---

@reports_bp.route('/orders', methods=['GET'])
@jwt_required()
def report_orders():
    """Orders report with date range, search, status filter."""
    q = Order.query.outerjoin(Customer, Order.customer_id == Customer.id)
    date_from = _parse_date(request.args.get('date_from'))
    date_to = _parse_date(request.args.get('date_to'))
    search = (request.args.get('search') or '').strip()
    status = request.args.get('status')
    if date_from:
        q = q.filter(func.date(Order.created_at) >= date_from)
    if date_to:
        q = q.filter(func.date(Order.created_at) <= date_to)
    if status:
        q = q.filter(Order.status == status)
    if search:
        conds = [
            Customer.full_name.ilike('%' + search + '%'),
            Order.clothing_type.ilike('%' + search + '%')
        ]
        if search.isdigit():
            conds.append(Order.id == int(search))
        q = q.filter(or_(*conds))
    q = q.order_by(Order.created_at.desc())
    pag = _paginate(q)
    items = []
    for o in pag.items:
        d = o.to_dict()
        d['customer'] = o.customer.to_dict() if o.customer else None
        items.append(d)
    return jsonify({'items': items, 'total': pag.total, 'pages': pag.pages, 'page': pag.page})


@reports_bp.route('/products', methods=['GET'])
@jwt_required()
def report_products():
    """Products/Inventory report."""
    q = Inventory.query
    search = (request.args.get('search') or '').strip()
    item_type = request.args.get('item_type')
    low_stock = request.args.get('low_stock', type=lambda x: x and str(x).lower() == 'true')
    if item_type:
        q = q.filter(Inventory.item_type == item_type)
    if low_stock:
        q = q.filter(Inventory.min_stock.isnot(None), Inventory.quantity <= Inventory.min_stock)
    if search:
        q = q.filter(or_(Inventory.name.ilike('%' + search + '%'), Inventory.item_type.ilike('%' + search + '%')))
    q = q.order_by(Inventory.name)
    pag = _paginate(q)
    items = [i.to_dict() for i in pag.items]
    return jsonify({'items': items, 'total': pag.total, 'pages': pag.pages, 'page': pag.page})


@reports_bp.route('/transactions', methods=['GET'])
@jwt_required()
def report_transactions():
    """Transactions report with date range, search, currency, type filter."""
    q = Transaction.query
    date_from = _parse_date(request.args.get('date_from'))
    date_to = _parse_date(request.args.get('date_to'))
    search = (request.args.get('search') or '').strip()
    currency = request.args.get('currency')
    trans_type = request.args.get('transaction_type')
    if date_from:
        q = q.filter(func.date(Transaction.transaction_date) >= date_from)
    if date_to:
        q = q.filter(func.date(Transaction.transaction_date) <= date_to)
    if currency:
        q = q.filter(Transaction.currency == currency)
    if trans_type:
        q = q.filter(Transaction.transaction_type == trans_type)
    if search:
        q = q.filter(or_(
            Transaction.details.ilike('%' + search + '%'),
            Transaction.category.ilike('%' + search + '%'),
            Transaction.currency.ilike('%' + search + '%')
        ))
    q = q.order_by(Transaction.transaction_date.desc())
    pag = _paginate(q)
    items = [t.to_dict() for t in pag.items]
    return jsonify({'items': items, 'total': pag.total, 'pages': pag.pages, 'page': pag.page})


@reports_bp.route('/exchange', methods=['GET'])
@jwt_required()
def report_exchange():
    """Exchange report - swaps/currency exchange."""
    q = Swap.query
    date_from = _parse_date(request.args.get('date_from'))
    date_to = _parse_date(request.args.get('date_to'))
    search = (request.args.get('search') or '').strip()
    if date_from:
        q = q.filter(func.date(Swap.created_at) >= date_from)
    if date_to:
        q = q.filter(func.date(Swap.created_at) <= date_to)
    if search:
        q = q.filter(or_(
            Swap.details.ilike('%' + search + '%'),
            Swap.from_account.ilike('%' + search + '%'),
            Swap.to_account.ilike('%' + search + '%')
        ))
    q = q.order_by(Swap.created_at.desc())
    pag = _paginate(q)
    items = [s.to_dict() for s in pag.items]
    return jsonify({'items': items, 'total': pag.total, 'pages': pag.pages, 'page': pag.page})


@reports_bp.route('/swaps', methods=['GET'])
@jwt_required()
def report_swaps():
    """Swaps report with date range and search."""
    return report_exchange()  # Same data


@reports_bp.route('/accounts', methods=['GET'])
@jwt_required()
def report_accounts():
    """Account/Banks report."""
    q = Bank.query
    search = (request.args.get('search') or '').strip()
    if search:
        q = q.filter(or_(Bank.name.ilike('%' + search + '%'), Bank.account_number.ilike('%' + search + '%')))
    q = q.order_by(Bank.created_at.desc())
    pag = _paginate(q)
    items = [b.to_dict() for b in pag.items]
    return jsonify({'items': items, 'total': pag.total, 'pages': pag.pages, 'page': pag.page})

@reports_bp.route('/sales', methods=['GET'])
@jwt_required()
def sales_report():
    period = request.args.get('period', 'daily')  # daily, weekly, monthly
    today = datetime.utcnow().date()
    if period == 'daily':
        start = today
        end = today
    elif period == 'weekly':
        start = today - timedelta(days=today.weekday())
        end = today
    else:
        start = today.replace(day=1)
        end = today
    # Revenue from orders (advance_paid + completed full payments)
    orders = Order.query.filter(
        Order.status.in_(['completed', 'delivered']),
        func.date(Order.updated_at) >= start,
        func.date(Order.updated_at) <= end
    ).all()
    total_revenue = sum((o.total_price or 0) for o in orders)
    total_orders = len(orders)
    # By clothing type
    by_type = {}
    for o in orders:
        by_type[o.clothing_type] = by_type.get(o.clothing_type, 0) + 1
    return jsonify({
        'period': period,
        'start': str(start),
        'end': str(end),
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'by_clothing_type': by_type
    })

@reports_bp.route('/income', methods=['GET'])
@jwt_required()
def daily_income():
    day = request.args.get('date')
    if day:
        try:
            target = datetime.strptime(day, '%Y-%m-%d').date()
        except ValueError:
            target = datetime.utcnow().date()
    else:
        target = datetime.utcnow().date()
    payments = Payment.query.filter(func.date(Payment.created_at) == target).all()
    total = sum(p.amount for p in payments)
    return jsonify({
        'date': str(target),
        'total_income': total,
        'payments_count': len(payments),
        'payments': [p.to_dict() for p in payments]
    })

@reports_bp.route('/best-customers', methods=['GET'])
@jwt_required()
def best_customers():
    limit = request.args.get('limit', 10, type=int)
    # Customers by order count and total spent
    q = db.session.query(
        Customer.id,
        Customer.full_name,
        Customer.phone,
        func.count(Order.id).label('order_count'),
        func.coalesce(func.sum(Order.total_price), 0).label('total_spent')
    ).outerjoin(Order).group_by(Customer.id).order_by(func.count(Order.id).desc())
    rows = q.limit(limit).all()
    return jsonify([{
        'id': r.id, 'full_name': r.full_name, 'phone': r.phone,
        'order_count': r.order_count, 'total_spent': float(r.total_spent)
    } for r in rows])

@reports_bp.route('/staff-performance', methods=['GET'])
@jwt_required()
def staff_performance():
    from models import User, Task
    staff = User.query.filter(User.role == 'tailor').all()
    out = []
    for u in staff:
        tasks = Task.query.filter_by(assigned_to=u.id).all()
        completed = [t for t in tasks if t.status == 'completed']
        out.append({
            'user': u.to_dict(),
            'total_tasks': len(tasks),
            'completed_tasks': len(completed),
            'completion_rate': len(completed) / len(tasks) * 100 if tasks else 0
        })
    return jsonify(out)
