"""
Database Setup Script
Run this to initialize the database and create default admin user
"""
import os
from app import app, db
from models import User

def setup_database():
    """Initialize database tables and create default admin user"""
    with app.app_context():
        try:
            print("Creating database tables...")
            db.create_all()
            print("✓ Tables created successfully")
            
            # Check if admin exists
            admin = User.query.filter_by(role='admin').first()
            if not admin:
                print("Creating default admin user...")
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
                print("✓ Default admin created:")
                print("  Email: admin@tailor.com")
                print("  Password: admin123")
            else:
                print(f"✓ Admin user already exists: {admin.email}")
            
            # Count users
            user_count = User.query.count()
            print(f"\n✓ Database setup complete! Total users: {user_count}")
            
        except Exception as e:
            print(f"✗ Error: {str(e)}")
            print("\nPlease check:")
            print("  1. MySQL server is running")
            print("  2. Database 'tailor_db' exists")
            print("  3. Connection string in config.py is correct")
            print("  4. PyMySQL is installed: pip install PyMySQL")
            raise

if __name__ == '__main__':
    setup_database()
