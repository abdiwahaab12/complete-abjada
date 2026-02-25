import json
import secrets
from datetime import datetime, timedelta
from extensions import db, bcrypt

class User(db.Model):
    __tablename__ = 'users'
    
    # Authentication fields
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')  # admin, tailor, cashier, user
    is_active = db.Column(db.Boolean, default=False)  # Must verify email first
    email_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(100), unique=True)
    verification_token_expires = db.Column(db.DateTime)
    failed_login_attempts = db.Column(db.Integer, default=0)
    account_locked_until = db.Column(db.DateTime)
    last_login_at = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String(45))
    current_login_at = db.Column(db.DateTime)
    current_login_ip = db.Column(db.String(45))
    login_count = db.Column(db.Integer, default=0)
    
    # Profile fields
    full_name = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    profile_image = db.Column(db.String(255))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Token fields
    reset_token = db.Column(db.String(100), index=True)
    reset_token_expires = db.Column(db.DateTime)
    refresh_token = db.Column(db.String(255), index=True)
    
    # Relationships
    assigned_orders = db.relationship('Order', backref='assignee', lazy='dynamic',
                                    foreign_keys='Order.assigned_to')
    tasks = db.relationship('Task', backref='assignee', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic', foreign_keys='Notification.user_id')

    # Password management
    def set_password(self, password):
        """Hash and set the user's password."""
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def check_password(self, password):
        """Check if the provided password matches the stored hash."""
        if not self.password_hash:
            return False
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def generate_verification_token(self, expires_in=3600):
        """Generate a verification token for email confirmation."""
        self.verification_token = secrets.token_urlsafe(32)
        self.verification_token_expires = datetime.utcnow() + timedelta(seconds=expires_in)
        return self.verification_token
    
    def generate_reset_token(self, expires_in=3600):
        """Generate a password reset token."""
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expires = datetime.utcnow() + timedelta(seconds=expires_in)
        return self.reset_token
    
    def verify_reset_token(token):
        """Verify the reset token and return the user if valid."""
        user = User.query.filter_by(reset_token=token).first()
        if user and user.reset_token_expires > datetime.utcnow():
            return user
        return None
    
    def record_login(self, ip_address):
        """Record successful login information."""
        self.last_login_at = self.current_login_at
        self.last_login_ip = self.current_login_ip
        self.current_login_at = datetime.utcnow()
        self.current_login_ip = ip_address
        self.login_count += 1
        self.failed_login_attempts = 0
        self.account_locked_until = None
    
    def record_failed_login(self):
        """Record a failed login attempt and lock account if needed."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:  # Lock after 5 failed attempts
            self.account_locked_until = datetime.utcnow() + timedelta(minutes=30)
    
    def is_account_locked(self):
        """Check if the account is currently locked."""
        if self.account_locked_until:
            if datetime.utcnow() < self.account_locked_until:
                return True
            self.account_locked_until = None  # Unlock if time has passed
            self.failed_login_attempts = 0
        return False
    
    def has_role(self, role_name):
        """Check if user has the specified role."""
        return self.role == role_name
    
    def has_any_role(self, *roles):
        """Check if user has any of the specified roles."""
        return self.role in roles
    
    @property
    def is_admin(self):
        """Check if user has admin role."""
        return self.role == 'admin'
    
    @property
    def is_staff(self):
        """Check if user is staff (admin, tailor, or cashier)."""
        return self.role in ('admin', 'tailor', 'cashier')
    
    def to_dict(self):
        """Return user data as dictionary."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'full_name': self.full_name,
            'phone': self.phone,
            'is_active': self.is_active,
            'email_verified': self.email_verified,
            'profile_image': self.profile_image,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'login_count': self.login_count
        }


class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    special_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    measurements = db.relationship('Measurement', backref='customer', lazy='dynamic', cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='customer', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id, 'full_name': self.full_name, 'phone': self.phone,
            'email': self.email, 'address': self.address, 'special_notes': self.special_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Measurement(db.Model):
    __tablename__ = 'measurements'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    profile_type = db.Column(db.String(20), default='standard')  # men, women, kids, standard
    chest = db.Column(db.Float)
    waist = db.Column(db.Float)
    shoulder = db.Column(db.Float)
    length = db.Column(db.Float)
    sleeve = db.Column(db.Float)
    neck = db.Column(db.Float)
    hip = db.Column(db.Float)
    inseam = db.Column(db.Float)
    extra_fields = db.Column(db.Text)  # JSON for additional measurements
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        out = {
            'id': self.id, 'customer_id': self.customer_id, 'profile_type': self.profile_type,
            'chest': self.chest, 'waist': self.waist, 'shoulder': self.shoulder,
            'length': self.length, 'sleeve': self.sleeve, 'neck': self.neck,
            'hip': self.hip, 'inseam': self.inseam, 'extra_fields': self.extra_fields,
            'notes': self.notes, 'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if self.extra_fields:
            try:
                extra = json.loads(self.extra_fields)
                for k in ('outseam', 'height', 'weight'):
                    if k in extra and extra[k] is not None:
                        out[k] = extra[k]
            except Exception:
                pass
        return out


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    clothing_type = db.Column(db.String(50), nullable=False)  # Suit, Shirt, Dress, etc.
    fabric_details = db.Column(db.Text)
    design_description = db.Column(db.Text)
    design_image = db.Column(db.String(255))
    delivery_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed, delivered, cancelled
    total_price = db.Column(db.Float, default=0)
    advance_paid = db.Column(db.Float, default=0)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    payments = db.relationship('Payment', backref='order', lazy='dynamic', cascade='all, delete-orphan')
    task = db.relationship('Task', backref='order', uselist=False, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id, 'customer_id': self.customer_id, 'clothing_type': self.clothing_type,
            'fabric_details': self.fabric_details, 'design_description': self.design_description,
            'design_image': self.design_image, 'delivery_date': str(self.delivery_date) if self.delivery_date else None,
            'status': self.status, 'total_price': self.total_price, 'advance_paid': self.advance_paid,
            'assigned_to': self.assigned_to, 'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'remaining_balance': float(self.total_price or 0) - float(self.advance_paid or 0)
        }


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_type = db.Column(db.String(20), default='advance')  # advance, full, partial
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    def to_dict(self):
        return {
            'id': self.id, 'order_id': self.order_id, 'amount': self.amount,
            'payment_type': self.payment_type, 'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by
        }


class Transaction(db.Model):
    """Standalone shop transactions: KES/USD, cash/digital, IN/OUT."""
    __tablename__ = 'shop_transactions'
    id = db.Column(db.Integer, primary_key=True)
    currency = db.Column(db.String(10), default='KES', nullable=False)  # KES, USD
    category = db.Column(db.String(80))  # e.g. sales, expense, salary
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(10), default='in')  # in, out
    method = db.Column(db.String(20), default='cash')  # cash, digital
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    def to_dict(self):
        return {
            'id': self.id, 'currency': self.currency, 'category': self.category,
            'amount': self.amount, 'transaction_type': self.transaction_type,
            'method': self.method,
            'transaction_date': self.transaction_date.isoformat() if self.transaction_date else None,
            'details': self.details, 'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by
        }


class Swap(db.Model):
    """Swap between accounts: from/to account, cash and digital amounts."""
    __tablename__ = 'swaps'
    id = db.Column(db.Integer, primary_key=True)
    from_account = db.Column(db.String(20), nullable=False)  # KES, USD, etc.
    to_account = db.Column(db.String(20), nullable=False)
    from_cash_amount = db.Column(db.Float, default=0)
    from_digital_amount = db.Column(db.Float, default=0)
    to_cash_amount = db.Column(db.Float, default=0)
    to_digital_amount = db.Column(db.Float, default=0)
    exchange_rate = db.Column(db.Float)  # optional
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    def to_dict(self):
        return {
            'id': self.id, 'from_account': self.from_account, 'to_account': self.to_account,
            'from_cash_amount': self.from_cash_amount, 'from_digital_amount': self.from_digital_amount,
            'to_cash_amount': self.to_cash_amount, 'to_digital_amount': self.to_digital_amount,
            'exchange_rate': self.exchange_rate, 'details': self.details,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by
        }


class Bank(db.Model):
    """Bank account: taker_name, optional user assignment."""
    __tablename__ = 'banks'
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(40), nullable=False, unique=True)  # e.g. ACC-0039
    name = db.Column(db.String(120), nullable=False)  # taker name
    balance = db.Column(db.Float, default=0)  # can be negative
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assigned_user = db.relationship('User', backref='assigned_banks', foreign_keys=[user_id])

    def to_dict(self):
        u = self.assigned_user
        return {
            'id': self.id, 'account_number': self.account_number, 'name': self.name,
            'balance': self.balance, 'user_id': self.user_id,
            'user': {'id': u.id, 'username': u.username, 'full_name': u.full_name} if u else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column(db.Integer, primary_key=True)
    item_type = db.Column(db.String(30), nullable=False)  # fabric, button, zipper, etc.
    name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Float, default=0)
    unit = db.Column(db.String(20), default='pcs')
    min_stock = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_low_stock(self):
        return self.min_stock and self.quantity <= self.min_stock

    def to_dict(self):
        return {
            'id': self.id, 'item_type': self.item_type, 'name': self.name,
            'quantity': self.quantity, 'unit': self.unit, 'min_stock': self.min_stock,
            'is_low_stock': self.is_low_stock, 'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='assigned')  # assigned, in_progress, completed
    progress_notes = db.Column(db.Text)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'order_id': self.order_id, 'assigned_to': self.assigned_to,
            'status': self.status, 'progress_notes': self.progress_notes,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    recipient_type = db.Column(db.String(20))  # customer, staff
    recipient_id = db.Column(db.Integer)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # staff notifications
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    type = db.Column(db.String(30))  # order_ready, delivery_reminder, payment_reminder
    message = db.Column(db.Text)
    sent_sms = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'recipient_type': self.recipient_type, 'recipient_id': self.recipient_id,
            'order_id': self.order_id, 'type': self.type, 'message': self.message,
            'sent_sms': self.sent_sms, 'created_at': self.created_at.isoformat() if self.created_at else None
        }


# Low stock threshold (items remaining) for alert notifications
LOW_STOCK_ALERT_THRESHOLD = 5


class LowStockAlertRead(db.Model):
    """Tracks which low-stock alerts each user has marked as read."""
    __tablename__ = 'low_stock_alert_read'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False, index=True)
    read_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'inventory_id', name='uq_low_stock_alert_read_user_inventory'),)
