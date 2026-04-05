import os
import re
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from werkzeug.utils import secure_filename
from sqlalchemy import cast, String
from extensions import db
from models import Order, Customer
from datetime import datetime
from finance_logic import (
    validate_order_amounts,
    sync_order_payment_status,
    apply_payment_status_payload,
    PRODUCT_ORDER_PLACEHOLDER_PHONE,
)

orders_bp = Blueprint('orders', __name__)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Tailor order workflow (also accepts legacy: pending, in_progress, completed)
ALLOWED_ORDER_STATUSES = frozenset({
    'order_received', 'measurements_recorded', 'fabric_added', 'cutting', 'sewing',
    'finishing', 'ready_for_delivery', 'delivered', 'cancelled',
    'pending', 'in_progress', 'completed',
})

# Sentinel phone so we can find the same row across restarts (product / walk-in orders).
PRODUCT_ORDER_CUSTOMER_PHONE = PRODUCT_ORDER_PLACEHOLDER_PHONE

def get_or_create_product_order_customer():
    """Placeholder customer for orders with no named customer (product-only sales)."""
    c = Customer.query.filter_by(phone=PRODUCT_ORDER_CUSTOMER_PHONE).first()
    if c:
        return c
    c = Customer(
        full_name='Product order',
        phone=PRODUCT_ORDER_CUSTOMER_PHONE,
        email=None,
        address=None,
        special_notes='System: orders without a specific customer.',
    )
    db.session.add(c)
    db.session.commit()
    return c

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _paginate(q, default_per=20):
    page = request.args.get('page', 1, type=int)
    per = request.args.get('per_page', default_per, type=int)
    per = min(per, 100)
    return q.paginate(page=page, per_page=per, error_out=False)

@orders_bp.route('', methods=['GET'])
@jwt_required()
def list_orders():
    from role_helpers import is_employee_role

    claims = get_jwt()
    q = Order.query
    # kind=tailor → real customer orders (exclude system "Product order" placeholder).
    # kind=stock → orders tied to empty-stock / product-only flow (placeholder customer only).
    kind = (request.args.get('kind') or '').strip().lower()
    product_placeholder = Customer.query.filter_by(phone=PRODUCT_ORDER_CUSTOMER_PHONE).first()
    # Employees only see tailor (customer) orders, never stock/product placeholder orders.
    if is_employee_role(claims.get('role')):
        if product_placeholder:
            q = q.filter(Order.customer_id != product_placeholder.id)
    elif kind in ('tailor', 'customer'):
        if product_placeholder:
            q = q.filter(Order.customer_id != product_placeholder.id)
    elif kind in ('stock', 'product', 'inventory'):
        if product_placeholder:
            q = q.filter(Order.customer_id == product_placeholder.id)
        else:
            q = q.filter(Order.id == -1)

    status = request.args.get('status')
    customer_id = request.args.get('customer_id', type=int)
    search = (request.args.get('search') or '').strip()
    if status:
        q = q.filter(Order.status == status)
    if customer_id:
        q = q.filter(Order.customer_id == customer_id)
    if search:
        digits = re.sub(r'\D', '', search)
        if digits:
            try:
                q = q.filter(Order.id == int(digits))
            except ValueError:
                q = q.filter(Order.id == -1)
        else:
            q = q.filter(cast(Order.id, String).ilike('%' + search + '%'))
    pag = _paginate(q.order_by(Order.created_at.desc()))
    items = []
    for o in pag.items:
        d = o.to_dict()
        d['customer'] = o.customer.to_dict() if o.customer else None
        items.append(d)
    return jsonify({
        'items': items,
        'total': pag.total,
        'pages': pag.pages or 1,
        'page': pag.page,
        'per_page': pag.per_page,
    })

@orders_bp.route('/<int:oid>', methods=['GET'])
@jwt_required()
def get_order(oid):
    o = Order.query.get(oid)
    if not o:
        return jsonify({'error': 'Order not found'}), 404
    d = o.to_dict()
    d['customer'] = o.customer.to_dict() if o.customer else None
    d['payments'] = [p.to_dict() for p in o.payments]
    return jsonify(d)

@orders_bp.route('', methods=['POST'])
@jwt_required()
def create_order():
    from role_helpers import is_employee_role

    claims = get_jwt()
    data = request.get_json() or {}
    # customer_id is optional: product-only / shipment orders use a system placeholder row.
    raw_cid = data.get('customer_id')
    customer_id = None
    if raw_cid is not None and raw_cid != '':
        try:
            customer_id = int(raw_cid)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid customer_id'}), 400
        if not Customer.query.get(customer_id):
            return jsonify({'error': 'Customer not found'}), 400
    else:
        if is_employee_role(claims.get('role')):
            return jsonify({'error': 'Employees must create tailor orders with a customer selected'}), 403
        customer_id = get_or_create_product_order_customer().id

    cust = Customer.query.get(customer_id)
    if cust and cust.phone == PRODUCT_ORDER_CUSTOMER_PHONE and is_employee_role(claims.get('role')):
        return jsonify({'error': 'Access denied'}), 403

    # clothing_type is a legacy column label (not shown on product order UI). Optional in API.
    clothing_type = (data.get('clothing_type') or '').strip() or 'Product order'
    delivery = data.get('delivery_date')
    if delivery:
        try:
            delivery = datetime.strptime(delivery, '%Y-%m-%d').date()
        except ValueError:
            delivery = None
    st = (data.get('status') or 'order_received').strip()
    if st not in ALLOWED_ORDER_STATUSES:
        st = 'order_received'

    o = Order(
        customer_id=customer_id,
        clothing_type=clothing_type,
        fabric_details=data.get('fabric_details'),
        design_description=data.get('design_description'),
        design_image=data.get('design_image'),
        delivery_date=delivery,
        status=st,
        total_price=float(data.get('total_price') or 0),
        advance_paid=float(data.get('advance_paid') or 0),
        assigned_to=data.get('assigned_to')
    )
    apply_payment_status_payload(o, data)
    ok, msg = validate_order_amounts(o.total_price, o.advance_paid)
    if not ok:
        return jsonify({'error': msg}), 400
    sync_order_payment_status(o)
    db.session.add(o)
    db.session.commit()
    return jsonify(o.to_dict()), 201

@orders_bp.route('/upload-design', methods=['POST'])
@jwt_required()
def upload_design():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(f.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    from flask import current_app
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'static/uploads')
    os.makedirs(upload_folder, exist_ok=True)
    filename = secure_filename(f.filename)
    base, ext = os.path.splitext(filename)
    filename = f"{base}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{ext}"
    path = os.path.join(upload_folder, filename)
    f.save(path)
    return jsonify({'design_image': f'/static/uploads/{filename}', 'filename': filename})

@orders_bp.route('/<int:oid>', methods=['PUT'])
@jwt_required()
def update_order(oid):
    o = Order.query.get(oid)
    if not o:
        return jsonify({'error': 'Order not found'}), 404
    data = request.get_json() or {}
    for key in ('clothing_type', 'fabric_details', 'design_description', 'design_image',
                'total_price', 'advance_paid', 'assigned_to'):
        if key in data:
            setattr(o, key, data[key])
    apply_payment_status_payload(o, data)
    ok, msg = validate_order_amounts(o.total_price, o.advance_paid)
    if not ok:
        return jsonify({'error': msg}), 400
    sync_order_payment_status(o)
    if 'status' in data:
        st = (data.get('status') or '').strip()
        if st in ALLOWED_ORDER_STATUSES:
            o.status = st
    if 'delivery_date' in data and data['delivery_date']:
        try:
            o.delivery_date = datetime.strptime(data['delivery_date'], '%Y-%m-%d').date()
        except ValueError:
            pass
    db.session.commit()
    return jsonify(o.to_dict())

@orders_bp.route('/<int:oid>', methods=['DELETE'])
@jwt_required()
def cancel_order(oid):
    o = Order.query.get(oid)
    if not o:
        return jsonify({'error': 'Order not found'}), 404
    o.status = 'cancelled'
    db.session.commit()
    return jsonify(o.to_dict())
