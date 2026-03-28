from flask import Blueprint, send_from_directory, redirect, request
import os

pages_bp = Blueprint('pages', __name__)
BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')


@pages_bp.route('/')
def index():
    return send_from_directory(BASE, 'index.html')


@pages_bp.route('/login')
def login_page():
    return send_from_directory(BASE, 'login.html')


@pages_bp.route('/dashboard')
def dashboard():
    return send_from_directory(BASE, 'dashboard.html')


@pages_bp.route('/dashboard/categories')
@pages_bp.route('/dashboard/categories/')
def dashboard_categories_mislink():
    """If the browser resolves a relative link wrong, /dashboard/categories still works."""
    return redirect('/category-page', code=302)


@pages_bp.route('/customers')
def customers():
    return send_from_directory(BASE, 'customers.html')


@pages_bp.route('/customers/add')
def customer_add():
    return send_from_directory(BASE, 'customer_add.html')


@pages_bp.route('/orders')
def orders():
    return send_from_directory(BASE, 'orders.html')


@pages_bp.route('/measurements')
def measurements():
    return send_from_directory(BASE, 'measurements.html')


@pages_bp.route('/payments')
def payments():
    return send_from_directory(BASE, 'payments.html')


@pages_bp.route('/transactions')
def transactions():
    return send_from_directory(BASE, 'transactions.html')


@pages_bp.route('/swap')
def swap():
    return send_from_directory(BASE, 'swap.html')


@pages_bp.route('/banks')
def banks():
    return send_from_directory(BASE, 'banks.html')


@pages_bp.route('/stock')
def stock():
    # Legacy sidebar URL: /stock?section=category
    if request.args.get('section') == 'category':
        return redirect('/category-page', code=302)
    return send_from_directory(BASE, 'inventory.html')


@pages_bp.route('/store')
def store():
    return send_from_directory(BASE, 'store.html')


# Same BASE as /store — if Products loads, this path must resolve the same way.
@pages_bp.route('/category-page')
@pages_bp.route('/category-page/')
@pages_bp.route('/categories')
@pages_bp.route('/categories/')
@pages_bp.route('/product-categories')
@pages_bp.route('/product-categories/')
@pages_bp.route('/category')
@pages_bp.route('/category/')
def category_admin_page():
    return send_from_directory(BASE, 'categories.html')


@pages_bp.route('/store/categories')
@pages_bp.route('/store/categories/')
def store_categories_alias():
    """Extra alias (Products live under /store; some users expect category next to that path)."""
    return redirect('/category-page', code=302)


@pages_bp.route('/tasks')
def tasks():
    return send_from_directory(BASE, 'tasks.html')


@pages_bp.route('/reports')
@pages_bp.route('/reports/<path:section>')
def reports(section=None):
    return send_from_directory(BASE, 'reports.html')


@pages_bp.route('/staff')
def staff():
    return send_from_directory(BASE, 'staff.html')


@pages_bp.route('/settings')
def settings():
    return send_from_directory(BASE, 'settings.html')
