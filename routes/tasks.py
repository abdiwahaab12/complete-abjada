from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import Task, Order, User

tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('', methods=['GET'])
@jwt_required()
def list_tasks():
    assigned_to = request.args.get('assigned_to', type=int)
    order_id = request.args.get('order_id', type=int)
    status = request.args.get('status')
    q = Task.query
    if assigned_to is not None:
        q = q.filter(Task.assigned_to == assigned_to)
    if order_id is not None:
        q = q.filter(Task.order_id == order_id)
    if status:
        q = q.filter(Task.status == status)
    tasks = q.order_by(Task.created_at.desc()).all()
    out = []
    for t in tasks:
        d = t.to_dict()
        d['order'] = t.order.to_dict() if t.order else None
        d['assigned_user'] = User.query.get(t.assigned_to).to_dict() if User.query.get(t.assigned_to) else None
        out.append(d)
    return jsonify(out)

@tasks_bp.route('/<int:tid>', methods=['GET'])
@jwt_required()
def get_task(tid):
    t = Task.query.get(tid)
    if not t:
        return jsonify({'error': 'Task not found'}), 404
    d = t.to_dict()
    d['order'] = t.order.to_dict() if t.order else None
    d['customer'] = t.order.customer.to_dict() if t.order and t.order.customer else None
    return jsonify(d)

@tasks_bp.route('', methods=['POST'])
@jwt_required()
def create_task():
    data = request.get_json() or {}
    order_id = data.get('order_id')
    assigned_to = data.get('assigned_to')
    if not order_id or not assigned_to:
        return jsonify({'error': 'order_id and assigned_to required'}), 400
    if not Order.query.get(order_id):
        return jsonify({'error': 'Order not found'}), 404
    if not User.query.get(assigned_to):
        return jsonify({'error': 'User not found'}), 404
    existing = Task.query.filter_by(order_id=order_id).first()
    if existing:
        return jsonify({'error': 'Order already has a task', 'task': existing.to_dict()}), 400
    t = Task(order_id=order_id, assigned_to=assigned_to, status='assigned')
    db.session.add(t)
    order = Order.query.get(order_id)
    order.assigned_to = assigned_to
    order.status = 'in_progress'
    db.session.commit()
    return jsonify(t.to_dict()), 201

@tasks_bp.route('/<int:tid>', methods=['PUT'])
@jwt_required()
def update_task(tid):
    t = Task.query.get(tid)
    if not t:
        return jsonify({'error': 'Task not found'}), 404
    data = request.get_json() or {}
    if 'status' in data:
        t.status = data['status']
        if data['status'] == 'completed':
            t.completed_at = datetime.utcnow()
            if t.order:
                t.order.status = 'completed'
    if 'progress_notes' in data:
        t.progress_notes = data['progress_notes']
    db.session.commit()
    return jsonify(t.to_dict())
