from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import Payment, Order, Customer

payments_bp = Blueprint('payments', __name__)

def _paginate(q, default_per=20):
    page = request.args.get('page', 1, type=int)
    per = request.args.get('per_page', default_per, type=int)
    per = min(per, 100)
    return q.paginate(page=page, per_page=per, error_out=False)


@payments_bp.route('/transactions', methods=['GET'])
@jwt_required()
def list_transactions():
    """List all payments (transactions) with order and customer info for Transactions page."""
    q = Payment.query.order_by(Payment.created_at.desc())
    pag = _paginate(q)
    items = []
    for p in pag.items:
        d = p.to_dict()
        if p.order:
            d['order'] = p.order.to_dict()
            d['customer_name'] = p.order.customer.full_name if p.order.customer else None
            d['order_total'] = p.order.total_price
            d['order_paid'] = p.order.advance_paid
        else:
            d['order'] = None
            d['customer_name'] = None
            d['order_total'] = None
            d['order_paid'] = None
        items.append(d)
    return jsonify({
        'items': items,
        'total': pag.total,
        'pages': pag.pages,
        'page': pag.page
    })


@payments_bp.route('', methods=['GET'])
@jwt_required()
def list_payments():
    order_id = request.args.get('order_id', type=int)
    if not order_id:
        return jsonify({'error': 'order_id required'}), 400
    payments = Payment.query.filter_by(order_id=order_id).order_by(Payment.created_at.desc()).all()
    return jsonify([p.to_dict() for p in payments])

@payments_bp.route('', methods=['POST'])
@jwt_required()
def create_payment():
    data = request.get_json() or {}
    order_id = data.get('order_id')
    amount = data.get('amount')
    if not order_id or amount is None:
        return jsonify({'error': 'order_id and amount required'}), 400
    order = Order.query.get(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    amount = float(amount)
    p = Payment(
        order_id=order_id,
        amount=amount,
        payment_type=data.get('payment_type', 'partial'),
        notes=data.get('notes'),
        created_by=get_jwt_identity()
    )
    db.session.add(p)
    order.advance_paid = (order.advance_paid or 0) + amount
    db.session.commit()
    return jsonify(p.to_dict()), 201


@payments_bp.route('/invoice/<int:order_id>', methods=['GET'])
@jwt_required()
def invoice_pdf(order_id):
    order = Order.query.get(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    customer = order.customer
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404
    payments = list(order.payments)
    from utils.invoice import generate_invoice_pdf
    buffer = generate_invoice_pdf(order, customer, payments)
    return send_file(
        buffer, mimetype='application/pdf',
        as_attachment=True, download_name=f'invoice_order_{order_id}.pdf'
    )
