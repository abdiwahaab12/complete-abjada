import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from extensions import db
from models import Measurement, Customer, FabricUsage, Inventory, ProductColor
from services.fabric_service import sync_measurement_fabric, restore_fabric_for_usage
from services.yard_breakdown import resolve_fabric_totals

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


def _parse_float(val, default=None):
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _resolve_product_from_color(product_color_id):
    if product_color_id is None:
        return None, None
    pc = ProductColor.query.get(int(product_color_id))
    if not pc:
        return None, 'Invalid product_color_id'
    return pc.product_id, None


def _raw_yard_breakdown_from_payload(data):
    if 'yard_breakdown' in data:
        return data.get('yard_breakdown')
    if 'fabric_yard_breakdown' in data:
        return data.get('fabric_yard_breakdown')
    return None


def _merge_fabric_update(measurement, data):
    """Returns (fabric_yards, fabric_yard_breakdown_json, error_message)."""
    has_bd = 'yard_breakdown' in data or 'fabric_yard_breakdown' in data
    raw_bd = _raw_yard_breakdown_from_payload(data) if has_bd else None
    if has_bd:
        fy_arg = data['fabric_yards'] if 'fabric_yards' in data else None
        fy, bd_json, err, _ = resolve_fabric_totals(fy_arg, raw_bd)
        return fy, bd_json, err
    if 'fabric_yards' in data:
        return _parse_float(data.get('fabric_yards')), measurement.fabric_yard_breakdown, None
    return measurement.fabric_yards, measurement.fabric_yard_breakdown, None


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

    product_color_id = data.get('product_color_id')
    if product_color_id is not None:
        product_color_id = int(product_color_id)
        pid, err = _resolve_product_from_color(product_color_id)
        if err:
            return jsonify({'error': err}), 400
        product_id = pid
    else:
        product_id = data.get('product_id')
        if product_id is not None:
            product_id = int(product_id)
            if not Inventory.query.get(product_id):
                return jsonify({'error': 'Invalid product_id'}), 400

    raw_bd = _raw_yard_breakdown_from_payload(data)
    fabric_yards, bd_json, res_err = resolve_fabric_totals(data.get('fabric_yards'), raw_bd)
    if res_err:
        return jsonify({'error': res_err}), 400

    pieces_to_deduct = _parse_float(data.get('pieces_to_deduct'), 0.0) or 0.0
    fy = float(fabric_yards) if fabric_yards is not None else 0.0

    extra_y = 0.0
    if product_color_id and pieces_to_deduct > 0:
        pc = ProductColor.query.get(product_color_id)
        if pc:
            extra_y = pieces_to_deduct * float(pc.yards_per_piece or 0)

    if (fy + extra_y > 0 or (pieces_to_deduct > 0 and not product_color_id)) and not product_id:
        return jsonify({'error': 'product_id or product_color_id is required when deducting stock'}), 400

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
        notes=data.get('notes'),
        product_id=product_id,
        product_color_id=product_color_id,
        fabric_yards=fabric_yards,
        fabric_yard_breakdown=bd_json,
        clothing_type=(data.get('clothing_type') or '').strip() or None,
    )
    db.session.add(m)
    db.session.flush()

    _, err = sync_measurement_fabric(
        m,
        old_usage=None,
        product_id=product_id,
        product_color_id=product_color_id,
        fabric_yards=fabric_yards,
        pieces_to_deduct=pieces_to_deduct,
    )
    if err:
        db.session.rollback()
        return jsonify({'error': err['error']}), err['status']

    db.session.commit()
    return jsonify(m.to_dict()), 201


@measurements_bp.route('/<int:mid>', methods=['PUT'])
@jwt_required()
def update_measurement(mid):
    m = Measurement.query.get(mid)
    if not m:
        return jsonify({'error': 'Measurement not found'}), 404
    data = request.get_json() or {}

    old_usage = FabricUsage.query.filter_by(measurement_id=m.id).first()

    product_id = m.product_id
    product_color_id = m.product_color_id
    fabric_yards = m.fabric_yards

    if 'product_color_id' in data:
        product_color_id = data.get('product_color_id')
        if product_color_id is not None:
            product_color_id = int(product_color_id)
            pid, err = _resolve_product_from_color(product_color_id)
            if err:
                return jsonify({'error': err}), 400
            product_id = pid
        else:
            product_color_id = None

    if 'product_id' in data and 'product_color_id' not in data:
        product_id = data.get('product_id')
        if product_id is not None:
            product_id = int(product_id)
            if not Inventory.query.get(product_id):
                return jsonify({'error': 'Invalid product_id'}), 400

    has_bd = 'yard_breakdown' in data or 'fabric_yard_breakdown' in data
    fabric_yards, bd_store, merge_err = _merge_fabric_update(m, data)
    if merge_err:
        return jsonify({'error': merge_err}), 400

    pieces_to_deduct = _parse_float(data.get('pieces_to_deduct'), 0.0)
    if pieces_to_deduct is None:
        pieces_to_deduct = 0.0
    if old_usage and 'pieces_to_deduct' not in data:
        pieces_to_deduct = float(old_usage.pieces_deducted or 0)

    for key in ('profile_type', 'chest', 'waist', 'shoulder', 'length', 'sleeve', 'neck', 'hip', 'inseam', 'notes'):
        if key in data:
            setattr(m, key, data[key])
    if any(k in data for k in ('outseam', 'height', 'weight', 'extra_fields')):
        m.extra_fields = _merge_extra(m.extra_fields, data)
    if 'clothing_type' in data:
        v = data.get('clothing_type')
        m.clothing_type = (v or '').strip() or None

    m.product_id = product_id
    m.product_color_id = product_color_id
    m.fabric_yards = fabric_yards
    if has_bd:
        m.fabric_yard_breakdown = bd_store

    fy_chk = float(fabric_yards) if fabric_yards is not None else 0.0
    extra_y = 0.0
    if product_color_id and pieces_to_deduct > 0:
        pc = ProductColor.query.get(product_color_id)
        if pc:
            extra_y = pieces_to_deduct * float(pc.yards_per_piece or 0)

    if (fy_chk + extra_y > 0 or (pieces_to_deduct > 0 and not product_color_id)) and not product_id:
        return jsonify({'error': 'product_id or product_color_id is required when deducting stock'}), 400

    db.session.flush()

    _, err = sync_measurement_fabric(
        m,
        old_usage=old_usage,
        product_id=product_id,
        product_color_id=product_color_id,
        fabric_yards=fabric_yards,
        pieces_to_deduct=pieces_to_deduct,
    )
    if err:
        db.session.rollback()
        return jsonify({'error': err['error']}), err['status']

    db.session.commit()
    return jsonify(m.to_dict())


@measurements_bp.route('/<int:mid>', methods=['DELETE'])
@jwt_required()
def delete_measurement(mid):
    m = Measurement.query.get(mid)
    if not m:
        return jsonify({'error': 'Measurement not found'}), 404
    u = FabricUsage.query.filter_by(measurement_id=m.id).first()
    if u:
        restore_fabric_for_usage(u)
        db.session.delete(u)
    db.session.delete(m)
    db.session.commit()
    return jsonify({'message': 'Deleted'}), 204
