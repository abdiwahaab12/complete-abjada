import os
from flask import Flask, send_from_directory, request, jsonify
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from sqlalchemy.engine.url import make_url
from extensions import db, bcrypt

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config.from_object('config.Config')

# Initialize extensions
db.init_app(app)
bcrypt.init_app(app)

jwt = JWTManager(app)
CORS(app, supports_credentials=True)


# Ensure MySQL database exists
def ensure_mysql_database():
    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if not uri.startswith('mysql'):
        return

    try:
        import pymysql
        u = make_url(uri)
        conn = pymysql.connect(
            host=u.host,
            user=u.username,
            password=u.password,
            port=u.port or 3306,
        )
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{u.database}`")
        conn.close()
    except Exception as e:
        print(f"MySQL ensure DB error: {e}")


# ✅ Import models AFTER db init (needed for db.create_all and routes)
from models import (
    User,
    Customer,
    Measurement,
    Order,
    Payment,
    Transaction,
    TransactionCategory,
    Liability,
    Expense,
    Swap,
    Bank,
    Inventory,
    FabricUsage,
    ProductColor,
    ProductCategory,
    Task,
    Notification,
    LowStockAlertRead,
    LowStockColorAlertRead,
)

# Ensure upload folder exists
os.makedirs(app.config.get('UPLOAD_FOLDER', 'static/uploads'), exist_ok=True)

# Register blueprints
from routes.auth import auth_bp
from routes.customers import customers_bp
from routes.orders import orders_bp
from routes.measurements import measurements_bp
from routes.payments import payments_bp
from routes.transactions import transactions_bp
from routes.transaction_categories import transaction_categories_bp
from routes.swaps import swaps_bp
from routes.banks import banks_bp
from routes.inventory import inventory_bp
from routes.product_colors import product_colors_bp
from routes.categories import categories_bp
from routes.tasks import tasks_bp
from routes.reports import reports_bp
from routes.dashboard import dashboard_bp
from routes.notifications import notifications_bp
from routes.pages import pages_bp
from routes.finance import finance_bp

app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(customers_bp, url_prefix='/api/customers')
app.register_blueprint(orders_bp, url_prefix='/api/orders')
app.register_blueprint(measurements_bp, url_prefix='/api/measurements')
app.register_blueprint(payments_bp, url_prefix='/api/payments')
app.register_blueprint(transactions_bp, url_prefix='/api/transactions')
app.register_blueprint(transaction_categories_bp, url_prefix='/api/transaction-categories')
app.register_blueprint(swaps_bp, url_prefix='/api/swaps')
app.register_blueprint(banks_bp, url_prefix='/api/banks')
app.register_blueprint(inventory_bp, url_prefix='/api/inventory')
app.register_blueprint(product_colors_bp, url_prefix='/api/inventory')
app.register_blueprint(categories_bp, url_prefix='/api/categories')
app.register_blueprint(tasks_bp, url_prefix='/api/tasks')
app.register_blueprint(reports_bp, url_prefix='/api/reports')
app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
app.register_blueprint(notifications_bp, url_prefix='/api/notifications')
app.register_blueprint(pages_bp)
app.register_blueprint(finance_bp, url_prefix='/api/finance')


@app.before_request
def enforce_api_role_access():
    """Block Employee role from financial / admin APIs (Super Admin unrestricted)."""
    from flask_jwt_extended import verify_jwt_in_request, get_jwt
    from role_helpers import is_super_admin_role, is_employee_role, employee_may_access_api_path

    if not request.path.startswith('/api/'):
        return
    if request.method == 'OPTIONS':
        return
    auth = request.headers.get('Authorization') or ''
    if not auth.startswith('Bearer '):
        return
    try:
        verify_jwt_in_request()
        claims = get_jwt()
    except Exception:
        return
    role = claims.get('role')
    if is_super_admin_role(role):
        return None
    if not is_employee_role(role):
        return None
    if employee_may_access_api_path(request.path, request.method):
        return None
    return jsonify({'error': 'Access denied for your role'}), 403


@app.route('/static/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/favicon.ico')
def favicon():
    """Avoid 404 noise in the console; browsers request /favicon.ico automatically."""
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'img'),
        'abjad-logo.png',
        mimetype='image/png',
    )


# Production-safe database initialization
with app.app_context():
    try:
        ensure_mysql_database()
        try:
            from schema_products import rename_inventory_to_products_if_needed
            rename_inventory_to_products_if_needed(db.engine)
        except Exception as e:
            print(f"✗ schema_products rename error: {e}")
        db.create_all()
        print("✓ Database tables created or already exist")
        try:
            from schema_finance import apply_finance_schema_patches
            apply_finance_schema_patches(db)
            print("✓ Finance schema patches applied")
        except Exception as e:
            print(f"✗ Finance schema patch error: {e}")
        try:
            from schema_fabric import apply_fabric_schema_patches
            apply_fabric_schema_patches(db)
            print("✓ Fabric / product yard schema patches applied")
        except Exception as e:
            print(f"✗ Fabric schema patch error: {e}")
        try:
            from schema_product_colors import apply_product_color_schema_patches
            apply_product_color_schema_patches(db)
            print("✓ Product color / measurement link schema patches applied")
        except Exception as e:
            print(f"✗ Product color schema patch error: {e}")

        # Create default admin user
        admin_user = User.query.filter_by(role='admin').first()
        if admin_user is None:
            admin = User(
                username='admin',
                email='admin@tailor.com',
                role='admin',
                full_name='Admin User',
                is_active=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✓ Default admin created")
        else:
            print("✓ Admin already exists")

        # Seed built-in categories only when the table is empty (first install).
        # Do not re-insert missing slugs on every startup — that would undo user deletes
        # after each server restart.
        if ProductCategory.query.count() == 0:
            for nm in ('khamis', 'shirt', 'fabric', 'button', 'zipper', 'thread', 'other'):
                db.session.add(ProductCategory(
                    public_id=ProductCategory.new_public_id(),
                    name=nm,
                    slug=nm,
                ))
            db.session.commit()
            print("✓ Default categories seeded (empty product_categories table)")
        else:
            print("✓ Product categories left as-is (no auto re-seed)")

        # Ensure transaction categories exist for any category names already used by transactions.
        try:
            distinct_cats = db.session.query(Transaction.category).distinct().all()
            existing = {c.name for c in TransactionCategory.query.all()}
            for (cat_name,) in distinct_cats:
                if not cat_name:
                    continue
                cat_name = str(cat_name).strip()
                if not cat_name or cat_name in existing:
                    continue
                db.session.add(TransactionCategory(
                    name=cat_name,
                    allowed_users='all',
                ))
            db.session.commit()
            print("✓ Transaction categories synced from existing transactions")
        except Exception as e:
            print(f"✗ Transaction category sync error: {e}")

        _cat_html = os.path.join(app.root_path, 'templates', 'categories.html')
        if os.path.isfile(_cat_html):
            print('✓ categories page template present (/category-page)')
        else:
            print(f'✗ Missing {_cat_html} — /category-page will 404')

    except Exception as e:
        print(f"✗ Database initialization error: {e}")


if __name__ == "__main__":
    # Local dev only. Default 5050: port 5000 is often taken on Windows (other Python runs, AirPlay, etc.)
    # and the browser then hits the wrong process → HTTP 404 / "invalid response".
    port = int(os.environ.get("PORT", "5050"))
    print(f"\n  Open in browser: http://127.0.0.1:{port}/\n")
    print(f"  Categories page: http://127.0.0.1:{port}/category-page\n")
    with app.test_client() as tc:
        ep = app.url_map.bind('').match('/category-page', method='GET')[0]
        print(f"  /category-page -> endpoint: {ep}")
        for _path in ('/category-page', '/store'):
            _r = tc.get(_path)
            if _r.status_code != 200:
                print(f"  ✗ Route self-test FAILED: {_path} -> {_r.status_code}")
            else:
                print(f"  ✓ Route self-test OK: {_path} -> 200 ({len(_r.data)} bytes)")
        _alt = tc.get('/product-categories')
        if _alt.status_code == 200 and len(_alt.data) > 1000:
            print('  ✓ /product-categories -> 200 (same HTML as /category-page)')
        else:
            print(f"  ✗ /product-categories check: {_alt.status_code}")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False, threaded=True)