import os
from flask import Flask, send_from_directory
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


# ✅ Import models AFTER db init
from models import (
    User,
    
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
from routes.swaps import swaps_bp
from routes.banks import banks_bp
from routes.inventory import inventory_bp
from routes.tasks import tasks_bp
from routes.reports import reports_bp
from routes.dashboard import dashboard_bp
from routes.notifications import notifications_bp
from routes.pages import pages_bp

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


@app.route('/static/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# Production-safe database initialization
with app.app_context():
    try:
        ensure_mysql_database()
        db.create_all()
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