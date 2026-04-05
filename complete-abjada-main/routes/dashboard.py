from datetime import datetime, timedelta
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import func
from extensions import db
from models import Order, Customer, Inventory, ProductColor

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('', methods=['GET'])
@jwt_required()
def stats():
    """
    Return high-level dashboard statistics.

    Uses Order.created_at for time-based calculations so it works
    with the current Order model (no updated_at column).
    """
    from role_helpers import is_employee_role, is_super_admin_role
    from routes.orders import PRODUCT_ORDER_CUSTOMER_PHONE

    claims = get_jwt()
    role = claims.get('role')
    if is_employee_role(role) and not is_super_admin_role(role):
        ph = Customer.query.filter_by(phone=PRODUCT_ORDER_CUSTOMER_PHONE).first()
        qo = Order.query
        if ph:
            qo = qo.filter(Order.customer_id != ph.id)
        tailor_orders = qo.count()
        active = Customer.query.count()
        open_tailor = qo.filter(
            Order.status.notin_(['delivered', 'completed', 'cancelled'])
        ).count()
        return jsonify({
            'mode': 'employee',
            'tailor_orders_total': tailor_orders,
            'tailor_orders_open': open_tailor,
            'active_customers': active,
        })

    total_orders = Order.query.count()
    completed = Order.query.filter(Order.status.in_(['completed', 'delivered'])).count()
    pending = Order.query.filter(Order.status == 'pending').count()
    in_progress = Order.query.filter(Order.status == 'in_progress').count()

    total_revenue = db.session.query(
        func.coalesce(func.sum(Order.total_price), 0)
    ).filter(
        Order.status.in_(['completed', 'delivered'])
    ).scalar() or 0

    active_customers = Customer.query.count()

    # Inventory-driven overview stats
    total_products = Inventory.query.count()
    color_variants_count = ProductColor.query.count()
    total_stock = db.session.query(
        func.coalesce(func.sum(Inventory.quantity), 0)
    ).scalar() or 0
    low_stock_items = Inventory.query.filter(
        Inventory.min_stock.isnot(None),
        Inventory.quantity <= Inventory.min_stock
    ).count()
    out_of_stock_items = Inventory.query.filter(
        func.coalesce(Inventory.quantity, 0) <= 0
    ).count()

    # This month revenue, based on created_at
    today = datetime.utcnow().date()
    month_start = today.replace(day=1)
    monthly_revenue = db.session.query(
        func.coalesce(func.sum(Order.total_price), 0)
    ).filter(
        Order.status.in_(['completed', 'delivered']),
        func.date(Order.created_at) >= month_start,
        func.date(Order.created_at) <= today
    ).scalar() or 0

    # Last 6 months for chart (approximate 30-day buckets)
    monthly_data = []
    for i in range(6):
        start = (today.replace(day=1) - timedelta(days=30 * (5 - i))).replace(day=1)
        end = start + timedelta(days=31)
        rev = db.session.query(
            func.coalesce(func.sum(Order.total_price), 0)
        ).filter(
            Order.status.in_(['completed', 'delivered']),
            func.date(Order.created_at) >= start,
            func.date(Order.created_at) <= end
        ).scalar() or 0
        # Profit is not explicitly stored; expose zero so frontend can render consistently.
        monthly_data.append({
            'month': start.strftime('%Y-%m'),
            'revenue': float(rev),
            'profit': 0.0
        })

    # Top products from completed/delivered orders (dynamic from real order data)
    top_rows = db.session.query(
        Order.clothing_type.label('product'),
        func.count(Order.id).label('quantity_sold'),
        func.coalesce(func.avg(Order.total_price), 0).label('avg_price'),
        func.coalesce(func.sum(Order.total_price), 0).label('total_sales')
    ).filter(
        Order.status.in_(['completed', 'delivered'])
    ).group_by(
        Order.clothing_type
    ).order_by(
        func.coalesce(func.sum(Order.total_price), 0).desc()
    ).limit(10).all()

    top_products = [{
        'product': (r.product or 'Unknown'),
        'quantity_sold': int(r.quantity_sold or 0),
        'price': float(r.avg_price or 0),
        'total_sales': float(r.total_sales or 0),
        'profit': 0.0
    } for r in top_rows]

    return jsonify({
        'mode': 'super_admin',
        'total_orders': total_orders,
        'completed_orders': completed,
        'pending_orders': pending,
        'in_progress_orders': in_progress,
        'total_revenue': float(total_revenue),
        'active_customers': active_customers,
        'monthly_revenue': float(monthly_revenue),
        'monthly_chart': monthly_data,
        'total_products': int(total_products or 0),
        'color_variants_count': int(color_variants_count or 0),
        'inventory_overview_url': '/api/inventory/overview',
        'inventory_yard_usage_report_url': '/api/inventory/yard-usage-report',
        'total_stock': float(total_stock or 0),
        'low_stock_items': int(low_stock_items or 0),
        'out_of_stock_items': int(out_of_stock_items or 0),
        'top_products': top_products,
    })
