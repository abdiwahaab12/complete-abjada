import os
from flask import Flask, send_from_directory
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from sqlalchemy.engine.url import make_url
from extensions import db, bcrypt

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config.from_object('config.Config')
db.init_app(app)


def ensure_mysql_database():
    """Create tailor_db if it does not exist (MySQL only)."""
    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if not uri.startswith('mysql'):
        return
    try:
        import pymysql
        u = make_url(uri)
        database = u.database or 'tailor_db'
        conn = pymysql.connect(
            host=u.host or 'localhost',
            user=u.username,
            password=u.password or None,
            port=u.port or 3306,
        )
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{database}`")
        conn.close()
    except Exception:
        pass  # e.g. DB already exists or no permission to create


jwt = JWTManager(app)
CORS(app, supports_credentials=True)

# Import after db is created
from models import User, Customer, Measurement, Order, Payment, Transaction, Swap, Bank, Inventory, Task, Notification, LowStockAlertRead

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

@app.cli.command()
def init_db():
    db.create_all()
    if User.query.filter_by(role='admin').first() is None:
        admin = User(username='admin', email='admin@tailor.com', role='admin', full_name='Admin', is_active=True)
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('Created default admin: admin / admin123')

if __name__ == '__main__':
    with app.app_context():
        try:
            ensure_mysql_database()
            db.create_all()
            # Add missing columns to existing tables (e.g. after model changes)
            try:
                from migrate_db import run_migrate
                run_migrate(app.config.get('SQLALCHEMY_DATABASE_URI'))
            except Exception as e:
                print(f"Note: migrate_db skipped or failed: {e}")
            print("✓ Database tables created successfully")
            
            # Create default admin user if it doesn't exist
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
                print("✓ Default admin user created:")
                print("  Email: admin@tailor.com")
                print("  Password: admin123")
            else:
                print(f"✓ Admin user already exists: {admin_user.email}")
        except Exception as e:
            print(f"✗ Database error: {str(e)}")
            print("Please ensure:")
            print("  1. MySQL is running")
            print("  2. Database 'tailor_db' exists (CREATE DATABASE tailor_db;)")
            print("  3. MySQL credentials are correct in config.py or .env")
            raise
    
    print("\n🚀 Starting Tailor Shop Management System...")
    print("📱 Access at: http://localhost:5000")
    app.run(debug=True, port=5000)
