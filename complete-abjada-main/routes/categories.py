import re
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import ProductCategory, Inventory

# JSON API only — mounted at /api/categories in app.py.
# HTML admin UI is served at /category-page (see routes.pages.category_admin_page).

categories_bp = Blueprint('categories', __name__)


def slugify(name):
    s = (name or '').strip().lower()
    try:
        import unicodedata
        t = unicodedata.normalize('NFKD', s)
        s = t.encode('ascii', 'ignore').decode('ascii')
    except Exception:
        pass
    s = re.sub(r'[^a-z0-9\s_-]', '', s)
    s = re.sub(r'[\s-]+', '_', s).strip('_')
    return s[:120] if s else 'category'


def unique_slug(base, exclude_id=None):
    slug = base
    n = 2
    while True:
        q = ProductCategory.query.filter_by(slug=slug)
        if exclude_id is not None:
            q = q.filter(ProductCategory.id != exclude_id)
        if not q.first():
            return slug
        slug = base + '_' + str(n)
        n += 1


def product_count_for_slug(slug):
    return Inventory.query.filter(Inventory.item_type == slug).count()


@categories_bp.route('', methods=['GET'])
@jwt_required()
def list_categories():
    page = request.args.get('page', 1, type=int) or 1
    per_raw = request.args.get('per_page', 20, type=int) or 20
    per = max(1, min(per_raw, 100))
    search = (request.args.get('search') or '').strip()
    sort = (request.args.get('sort') or 'name').lower()
    order = (request.args.get('order') or 'asc').lower()

    q = ProductCategory.query
    if search:
        q = q.filter(ProductCategory.name.ilike('%' + search + '%'))
    col = ProductCategory.name if sort == 'name' else ProductCategory.created_at
    q = q.order_by(col.desc() if order == 'desc' else col.asc())

    pag = q.paginate(page=page, per_page=per, error_out=False)
    items = []
    for c in pag.items:
        d = c.to_dict()
        d['product_count'] = product_count_for_slug(c.slug)
        items.append(d)
    resp = jsonify({
        'items': items,
        'total': pag.total,
        'page': pag.page,
        'pages': pag.pages,
        'per_page': pag.per_page,
    })
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    return resp


@categories_bp.route('', methods=['POST'])
@jwt_required()
def create_category():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    if ProductCategory.query.filter_by(name=name).first():
        return jsonify({'error': 'A category with this name already exists'}), 400
    base = slugify(name)
    slug = unique_slug(base)
    cat = ProductCategory(
        public_id=ProductCategory.new_public_id(),
        name=name,
        slug=slug,
    )
    db.session.add(cat)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Could not create category'}), 400
    return jsonify({**cat.to_dict(), 'product_count': 0}), 201


@categories_bp.route('/<int:cid>', methods=['PUT'])
@jwt_required()
def update_category(cid):
    cat = ProductCategory.query.get(cid)
    if not cat:
        return jsonify({'error': 'Not found'}), 404
    data = request.get_json() or {}
    name = data.get('name')
    if name is None:
        return jsonify({'error': 'name required'}), 400
    name = name.strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    other = ProductCategory.query.filter(
        ProductCategory.name == name,
        ProductCategory.id != cid,
    ).first()
    if other:
        return jsonify({'error': 'A category with this name already exists'}), 400

    old_slug = cat.slug
    cat.name = name
    new_base = slugify(name)
    new_slug = unique_slug(new_base, exclude_id=cid)
    if new_slug != old_slug:
        Inventory.query.filter_by(item_type=old_slug).update(
            {'item_type': new_slug},
            synchronize_session=False,
        )
        cat.slug = new_slug
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Could not update category'}), 400
    return jsonify({**cat.to_dict(), 'product_count': product_count_for_slug(cat.slug)})


@categories_bp.route('/<int:cid>', methods=['DELETE'])
@jwt_required()
def delete_category(cid):
    cat = ProductCategory.query.get(cid)
    if not cat:
        return jsonify({'error': 'Not found'}), 404
    if product_count_for_slug(cat.slug) > 0:
        return jsonify({'error': 'Cannot delete a category that still has products'}), 400
    db.session.delete(cat)
    db.session.commit()
    return jsonify({'ok': True})
