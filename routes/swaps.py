from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db
from models import Swap

swaps_bp = Blueprint('swaps', __name__)


def _paginate(q, default_per=25):
    page = request.args.get('page', 1, type=int)
    per = request.args.get('per_page', default_per, type=int)
    per = min(per, 100)
    return q.paginate(page=page, per_page=per, error_out=False)


@swaps_bp.route('', methods=['GET'])
@jwt_required()
def list_swaps():
    """List all swaps."""
    q = Swap.query.order_by(Swap.created_at.desc())
    pag = _paginate(q)
    items = [s.to_dict() for s in pag.items]
    return jsonify({
        'items': items,
        'total': pag.total,
        'pages': pag.pages,
        'page': pag.page
    })


@swaps_bp.route('', methods=['POST'])
@jwt_required()
def create_swap():
    """Create a new swap between accounts."""
    data = request.get_json() or {}
    from_account = (data.get('from_account') or '').strip() or 'KES'
    to_account = (data.get('to_account') or '').strip() or 'USD'
    from_cash = float(data.get('from_cash_amount', 0) or 0)
    from_digital = float(data.get('from_digital_amount', 0) or 0)
    to_cash = float(data.get('to_cash_amount', 0) or 0)
    to_digital = float(data.get('to_digital_amount', 0) or 0)
    exchange_rate = data.get('exchange_rate')
    if exchange_rate is not None:
        try:
            exchange_rate = float(exchange_rate)
        except (TypeError, ValueError):
            exchange_rate = None
    s = Swap(
        from_account=from_account,
        to_account=to_account,
        from_cash_amount=from_cash,
        from_digital_amount=from_digital,
        to_cash_amount=to_cash,
        to_digital_amount=to_digital,
        exchange_rate=exchange_rate,
        details=data.get('details'),
        created_by=get_jwt_identity()
    )
    db.session.add(s)
    db.session.commit()
    return jsonify(s.to_dict()), 201
