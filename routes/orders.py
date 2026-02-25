import os
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from werkzeug.utils import secure_filename
from extensions import db
from models import Order, Customer
from datetime import datetime

orders_bp = Blueprint('orders', __name__)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

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
    q = Order.query
    status = request.args.get('status')
    customer_id = request.args.get('customer_id', type=int)
    if status:
        q = q.filter(Order.status == status)
    if customer_id:
        q = q.filter(Order.customer_id == customer_id)
    pag = _paginate(q.order_by(Order.created_at.desc()))
    items = []
    for o in pag.items:
        d = o.to_dict()
        d['customer'] = o.customer.to_dict() if o.customer else None
        items.append(d)
    return jsonify({
        'items': items,
        'total': pag.total,
        'pages': pag.pages,
        'page': pag.page
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
    data = request.get_json() or {}
    customer_id = data.get('customer_id')
    clothing_type = data.get('clothing_type')
    if not customer_id or not clothing_type:
        return jsonify({'error': 'customer_id and clothing_type required'}), 400
    if not Customer.query.get(customer_id):
        return jsonify({'error': 'Customer not found'}), 400
    delivery = data.get('delivery_date')
    if delivery:
        try:
            delivery = datetime.strptime(delivery, '%Y-%m-%d').date()
        except ValueError:
            delivery = None
    o = Order(
        customer_id=customer_id,
        clothing_type=clothing_type,
        fabric_details=data.get('fabric_details'),
        design_description=data.get('design_description'),
        design_image=data.get('design_image'),
        delivery_date=delivery,
        status=data.get('status', 'pending'),
        total_price=float(data.get('total_price') or 0),
        advance_paid=float(data.get('advance_paid') or 0),
        assigned_to=data.get('assigned_to')
    )
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
    for key in ('clothing_type', 'fabric_details', 'design_description', 'design_image', 'status',
                'total_price', 'advance_paid', 'assigned_to'):
        if key in data:
            setattr(o, key, data[key])
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
