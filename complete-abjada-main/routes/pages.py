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


@pages_bp.route('/admin/login')
@pages_bp.route('/admin-login')
def admin_login_alias():
    # Force all admin-login style URLs to use the same normal login page.
    return redirect('/login', code=302)


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


@pages_bp.route('/orders/new')
def order_form_new():
    return send_from_directory(BASE, 'order_form.html')


@pages_bp.route('/orders/<int:order_id>/edit')
def order_form_edit(order_id):
    return send_from_directory(BASE, 'order_form.html')


@pages_bp.route('/orders')
def orders():
    return send_from_directory(BASE, 'orders.html')


@pages_bp.route('/invoice/<int:order_id>/print')
def invoice_print_page(order_id):
    """Print-friendly HTML invoice (browser print / Save as PDF)."""
    return send_from_directory(BASE, 'invoice_print.html')


@pages_bp.route('/measurements')
def measurements():
    return send_from_directory(BASE, 'measurements.html')


@pages_bp.route('/body-measurements')
def body_measurements():
    """Former measurements form (body sizes per customer)."""
    return send_from_directory(BASE, 'body_measurements.html')


@pages_bp.route('/payments')
def payments():
    return send_from_directory(BASE, 'payments.html')


@pages_bp.route('/transactions')
def transactions():
    return send_from_directory(BASE, 'transactions.html')


@pages_bp.route('/transaction-categories')
def transaction_categories_page():
    return send_from_directory(BASE, 'transaction_categories.html')


@pages_bp.route('/swap')
def swap():
    return send_from_directory(BASE, 'swap.html')


@pages_bp.route('/stock')
def stock():
    # Legacy sidebar URL: /stock?section=category
    if request.args.get('section') == 'category':
        return redirect('/category-page', code=302)
    return send_from_directory(BASE, 'inventory.html')


@pages_bp.route('/stock/add')
def stock_add_page():
    """Full-page form to add stock (no modal)."""
    return send_from_directory(BASE, 'stock_add.html')


@pages_bp.route('/store')
def store():
    return send_from_directory(BASE, 'store.html')


@pages_bp.route('/accounts')
def accounts_finance_page():
    """Financial management: reports, liabilities, expenses, customer profiles."""
    return send_from_directory(BASE, 'accounts.html')

@pages_bp.route('/products')
@pages_bp.route('/products/')
def products_list():
    return send_from_directory(BASE, 'store.html')


@pages_bp.route('/products/add')
@pages_bp.route('/products/add/')
def product_add_page():
    return send_from_directory(BASE, 'product_add.html')


@pages_bp.route('/products/preview')
@pages_bp.route('/products/preview/')
def product_preview_page():
    """Client-side-only product rows open here (sessionStorage)."""
    return send_from_directory(BASE, 'product_detail.html')


@pages_bp.route('/products/<int:product_id>')
def product_detail_page(product_id):
    return send_from_directory(BASE, 'product_detail.html')


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


@pages_bp.route('/user')
def user_page():
    return send_from_directory(BASE, 'user.html')


@pages_bp.route('/user/add')
def user_add_page():
    return send_from_directory(BASE, 'user_add.html')


@pages_bp.route('/help')
def help_page():
    return send_from_directory(BASE, 'help.html')
