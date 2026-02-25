import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from extensions import db
from models import Measurement, Customer

measurements_bp = Blueprint('measurements', __name__)


def _merge_extra(extra_fields, data):
    """Merge outseam, height, weight from data into extra_fields JSON."""
    extra = {}
    if extra_fields:
        try:
            extra = json.loads(extra_fields)
        except Exception:
            pass
    for k in ('outseam', 'height', 'weight'):
        if k in data and data[k] is not None:
            try:
                extra[k] = float(data[k])
            except (TypeError, ValueError):
                pass
    return json.dumps(extra) if extra else None

@measurements_bp.route('', methods=['GET'])
@jwt_required()
def list_measurements():
    customer_id = request.args.get('customer_id', type=int)
    if not customer_id:
        return jsonify({'error': 'customer_id required'}), 400
    ms = Measurement.query.filter_by(customer_id=customer_id).order_by(Measurement.created_at.desc()).all()
    return jsonify([m.to_dict() for m in ms])

@measurements_bp.route('/<int:mid>', methods=['GET'])
@jwt_required()
def get_measurement(mid):
    m = Measurement.query.get(mid)
    if not m:
        return jsonify({'error': 'Measurement not found'}), 404
    return jsonify(m.to_dict())

@measurements_bp.route('', methods=['POST'])
@jwt_required()
def create_measurement():
    data = request.get_json() or {}
    customer_id = data.get('customer_id')
    if not customer_id or not Customer.query.get(customer_id):
        return jsonify({'error': 'Valid customer_id required'}), 400
    m = Measurement(
        customer_id=customer_id,
        profile_type=data.get('profile_type', 'standard'),
        chest=data.get('chest'),
        waist=data.get('waist'),
        shoulder=data.get('shoulder'),
        length=data.get('length'),
        sleeve=data.get('sleeve'),
        neck=data.get('neck'),
        hip=data.get('hip'),
        inseam=data.get('inseam'),
        extra_fields=_merge_extra(data.get('extra_fields'), data),
        notes=data.get('notes')
    )
    db.session.add(m)
    db.session.commit()
    return jsonify(m.to_dict()), 201

@measurements_bp.route('/<int:mid>', methods=['PUT'])
@jwt_required()
def update_measurement(mid):
    m = Measurement.query.get(mid)
    if not m:
        return jsonify({'error': 'Measurement not found'}), 404
    data = request.get_json() or {}
    for key in ('profile_type', 'chest', 'waist', 'shoulder', 'length', 'sleeve', 'neck', 'hip', 'inseam', 'notes'):
        if key in data:
            setattr(m, key, data[key])
    if any(k in data for k in ('outseam', 'height', 'weight', 'extra_fields')):
        m.extra_fields = _merge_extra(m.extra_fields, data)
    db.session.commit()
    return jsonify(m.to_dict())

@measurements_bp.route('/<int:mid>', methods=['DELETE'])
@jwt_required()
def delete_measurement(mid):
    m = Measurement.query.get(mid)
    if not m:
        return jsonify({'error': 'Measurement not found'}), 404
    db.session.delete(m)
    db.session.commit()
    return jsonify({'message': 'Deleted'}), 204
