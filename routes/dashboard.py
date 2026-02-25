from datetime import datetime, timedelta
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func
from extensions import db
from models import Order, Customer, Payment

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('', methods=['GET'])
@jwt_required()
def stats():
    total_orders = Order.query.count()
    completed = Order.query.filter(Order.status.in_(['completed', 'delivered'])).count()
    pending = Order.query.filter(Order.status == 'pending').count()
    in_progress = Order.query.filter(Order.status == 'in_progress').count()
    total_revenue = db.session.query(func.coalesce(func.sum(Order.total_price), 0)).filter(
        Order.status.in_(['completed', 'delivered'])
    ).scalar() or 0
    active_customers = Customer.query.count()
    # This month revenue
    today = datetime.utcnow().date()
    month_start = today.replace(day=1)
    monthly_revenue = db.session.query(func.coalesce(func.sum(Order.total_price), 0)).filter(
        Order.status.in_(['completed', 'delivered']),
        func.date(Order.updated_at) >= month_start,
        func.date(Order.updated_at) <= today
    ).scalar() or 0
    # Last 6 months for chart (approximate 30-day buckets)
    monthly_data = []
    for i in range(6):
        start = (today.replace(day=1) - timedelta(days=30 * (5 - i))).replace(day=1)
        end = start + timedelta(days=31)
        rev = db.session.query(func.coalesce(func.sum(Order.total_price), 0)).filter(
            Order.status.in_(['completed', 'delivered']),
            func.date(Order.updated_at) >= start,
            func.date(Order.updated_at) <= end
        ).scalar() or 0
        monthly_data.append({'month': start.strftime('%Y-%m'), 'revenue': float(rev)})
    return jsonify({
        'total_orders': total_orders,
        'completed_orders': completed,
        'pending_orders': pending,
        'in_progress_orders': in_progress,
        'total_revenue': float(total_revenue),
        'active_customers': active_customers,
        'monthly_revenue': float(monthly_revenue),
        'monthly_chart': monthly_data
    })
