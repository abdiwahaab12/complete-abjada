import os
from flask import Flask, send_from_directory
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from sqlalchemy import inspect, text
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
    Category,
    TransactionCategory,
    OrderCategory,
    Swap,
    Bank,
    Inventory,
    Task,
    Notification,
    LowStockAlertRead,
)

# Ensure upload folder exists
os.makedirs(app.config.get('UPLOAD_FOLDER', 'static/uploads'), exist_ok=True)


def ensure_schema_updates():
    """Apply small additive schema updates for existing databases."""
    engine = db.engine
    inspector = inspect(engine)
    dialect = engine.dialect.name

    existing_tables = set(inspector.get_table_names())
    if 'orders' in existing_tables:
        cols = {c['name'] for c in inspector.get_columns('orders')}
        if 'category' not in cols:
            sql = "ALTER TABLE orders ADD COLUMN category VARCHAR(80)"
            with engine.begin() as conn:
                conn.execute(text(sql))

    if 'categories' in existing_tables:
        cols = {c['name'] for c in inspector.get_columns('categories')}
        if 'type' not in cols:
            sql = "ALTER TABLE categories ADD COLUMN type VARCHAR(20)"
            with engine.begin() as conn:
                conn.execute(text(sql))

    # Seed default transaction categories only if table exists.
    if 'transaction_categories' in existing_tables:
        defaults = ['sales', 'service', 'expense', 'salary', 'supplies', 'other']
        for name in defaults:
            if not TransactionCategory.query.filter(
                db.func.lower(TransactionCategory.name) == name.lower()
            ).first():
                db.session.add(TransactionCategory(name=name))
        db.session.commit()

    if 'order_categories' in existing_tables:
        defaults = ['Suit', 'Shirt', 'Dress', 'Trouser', 'Blouse', 'Coat', 'Other']
        for name in defaults:
            if not OrderCategory.query.filter(
                db.func.lower(OrderCategory.name) == name.lower()
            ).first():
                db.session.add(OrderCategory(name=name))
        db.session.commit()

    # Unified categories: migrate legacy names once, then seed defaults if empty
    if 'categories' in existing_tables:
        if Category.query.count() == 0:
            names = set()
            try:
                for row in TransactionCategory.query.all():
                    names.add(row.name)
            except Exception:
                pass
            try:
                for row in OrderCategory.query.all():
                    names.add(row.name)
            except Exception:
                pass
            for name in sorted(names, key=lambda x: x.lower()):
                if not Category.query.filter(
                    db.func.lower(Category.name) == name.lower()
                ).first():
                    ctype = None
                    if TransactionCategory.query.filter(
                        db.func.lower(TransactionCategory.name) == name.lower()
                    ).first():
                        ctype = 'transaction'
                    elif OrderCategory.query.filter(
                        db.func.lower(OrderCategory.name) == name.lower()
                    ).first():
                        ctype = 'order'
                    db.session.add(Category(name=name, type=ctype, description=None))
            db.session.commit()
        if Category.query.count() == 0:
            tx_defaults = ('sales', 'service', 'expense', 'salary', 'supplies', 'other')
            order_defaults = ('Suit', 'Shirt', 'Dress', 'Trouser', 'Blouse', 'Coat', 'Clothes')
            for name in tx_defaults:
                if not Category.query.filter(
                    db.func.lower(Category.name) == name.lower()
                ).first():
                    db.session.add(Category(name=name, type='transaction', description=None))
            for name in order_defaults:
                if not Category.query.filter(
                    db.func.lower(Category.name) == name.lower()
                ).first():
                    db.session.add(Category(name=name, type='order', description=None))
            db.session.commit()

        # Backfill missing type values for older records
        unresolved = Category.query.filter(
            db.or_(Category.type.is_(None), Category.type == '')
        ).all()
        order_name_defaults = {'suit', 'shirt', 'dress', 'trouser', 'blouse', 'coat', 'clothes'}
        for c in unresolved:
            tx_hit = Transaction.query.filter(Transaction.category == c.name).first() is not None
            od_hit = Order.query.filter(Order.category == c.name).first() is not None
            if tx_hit and not od_hit:
                c.type = 'transaction'
            elif od_hit and not tx_hit:
                c.type = 'order'
            elif TransactionCategory.query.filter(
                db.func.lower(TransactionCategory.name) == c.name.lower()
            ).first():
                c.type = 'transaction'
            elif OrderCategory.query.filter(
                db.func.lower(OrderCategory.name) == c.name.lower()
            ).first():
                c.type = 'order'
            elif c.name and c.name.lower() in order_name_defaults:
                c.type = 'order'
            else:
                c.type = 'transaction'
        db.session.commit()

# Register blueprints
from routes.auth import auth_bp
from routes.customers import customers_bp
from routes.orders import orders_bp
from routes.measurements import measurements_bp
from routes.payments import payments_bp
from routes.transactions import transactions_bp
from routes.swaps import swaps_bp
from routes.banks import banks_bp
from routes.inventory import inventory_bp
from routes.tasks import tasks_bp
from routes.reports import reports_bp
from routes.dashboard import dashboard_bp
from routes.notifications import notifications_bp
from routes.pages import pages_bp
from routes.categories import categories_bp

app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(customers_bp, url_prefix='/api/customers')
app.register_blueprint(orders_bp, url_prefix='/api/orders')
app.register_blueprint(measurements_bp, url_prefix='/api/measurements')
app.register_blueprint(payments_bp, url_prefix='/api/payments')
app.register_blueprint(transactions_bp, url_prefix='/api/transactions')
app.register_blueprint(swaps_bp, url_prefix='/api/swaps')
app.register_blueprint(banks_bp, url_prefix='/api/banks')
app.register_blueprint(inventory_bp, url_prefix='/api/inventory')
app.register_blueprint(tasks_bp, url_prefix='/api/tasks')
app.register_blueprint(reports_bp, url_prefix='/api/reports')
app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
app.register_blueprint(notifications_bp, url_prefix='/api/notifications')
app.register_blueprint(pages_bp)
app.register_blueprint(categories_bp, url_prefix='/api/categories')


@app.route('/static/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# Production-safe database initialization
with app.app_context():
    try:
        ensure_mysql_database()
        db.create_all()
        ensure_schema_updates()
        print("✓ Database tables created or already exist")

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

    except Exception as e:
        print(f"✗ Database initialization error: {e}")