import secrets
from datetime import datetime, timedelta
from extensions import db, bcrypt

# Low stock threshold for alert notifications
LOW_STOCK_ALERT_THRESHOLD = 5


class User(db.Model):
    __tablename__ = 'users'

    # ========================
    # Authentication fields
    # ========================
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    is_active = db.Column(db.Boolean, default=False)
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

    # ========================
    # Profile fields
    # ========================
    full_name = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    profile_image = db.Column(db.String(255))

    # ========================
    # Tokens
    # ========================
    reset_token = db.Column(db.String(100), index=True)
    reset_token_expires = db.Column(db.DateTime)
    refresh_token = db.Column(db.String(255), index=True)

    # ========================
    # Timestamps
    # ========================
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ========================
    # PASSWORD MANAGEMENT
    # ========================

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        if not self.password_hash:
            return False
        return bcrypt.check_password_hash(self.password_hash, password)

    # ========================
    # Token helpers
    # ========================

    def generate_verification_token(self, expires_in=3600):
        self.verification_token = secrets.token_urlsafe(32)
        self.verification_token_expires = datetime.utcnow() + timedelta(seconds=expires_in)
        return self.verification_token

    def generate_reset_token(self, expires_in=3600):
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expires = datetime.utcnow() + timedelta(seconds=expires_in)
        return self.reset_token

    @staticmethod
    def verify_reset_token(token):
        user = User.query.filter_by(reset_token=token).first()
        if user and user.reset_token_expires and user.reset_token_expires > datetime.utcnow():
            return user
        return None

    # ========================
    # Login tracking
    # ========================

    def record_login(self, ip_address):
        self.last_login_at = self.current_login_at
        self.last_login_ip = self.current_login_ip
        self.current_login_at = datetime.utcnow()
        self.current_login_ip = ip_address
        self.login_count = (self.login_count or 0) + 1
        self.failed_login_attempts = 0
        self.account_locked_until = None

    def record_failed_login(self):
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        if self.failed_login_attempts >= 5:
            self.account_locked_until = datetime.utcnow() + timedelta(minutes=30)

    def is_account_locked(self):
        if self.account_locked_until and datetime.utcnow() < self.account_locked_until:
            return True
        return False

    # ========================
    # Role helpers
    # ========================

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_staff(self):
        return self.role in ("admin", "tailor", "cashier")

    # ========================
    # Serialize
    # ========================

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "full_name": self.full_name,
            "phone": self.phone,
            "is_active": self.is_active,
            "email_verified": self.email_verified,
            "profile_image": self.profile_image,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "login_count": self.login_count,
        }


class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120))
    address = db.Column(db.String(255))
    special_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    measurements = db.relationship('Measurement', backref='customer', lazy='dynamic', cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='customer', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'phone': self.phone,
            'email': self.email,
            'address': self.address,
            'special_notes': self.special_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Measurement(db.Model):
    __tablename__ = 'measurements'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    profile_type = db.Column(db.String(40), default='standard')
    chest = db.Column(db.Float)
    waist = db.Column(db.Float)
    shoulder = db.Column(db.Float)
    length = db.Column(db.Float)
    sleeve = db.Column(db.Float)
    neck = db.Column(db.Float)
    hip = db.Column(db.Float)
    inseam = db.Column(db.Float)
    extra_fields = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'profile_type': self.profile_type,
            'chest': self.chest,
            'waist': self.waist,
            'shoulder': self.shoulder,
            'length': self.length,
            'sleeve': self.sleeve,
            'neck': self.neck,
            'hip': self.hip,
            'inseam': self.inseam,
            'extra_fields': self.extra_fields,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    clothing_type = db.Column(db.String(120), nullable=False)
    fabric_details = db.Column(db.String(255))
    design_description = db.Column(db.Text)
    design_image = db.Column(db.String(255))
    delivery_date = db.Column(db.Date)
    status = db.Column(db.String(30), default='pending')
    total_price = db.Column(db.Float, default=0)
    advance_paid = db.Column(db.Float, default=0)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    payments = db.relationship('Payment', backref='order', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'clothing_type': self.clothing_type,
            'fabric_details': self.fabric_details,
            'design_description': self.design_description,
            'design_image': self.design_image,
            'delivery_date': self.delivery_date.isoformat() if self.delivery_date else None,
            'status': self.status,
            'total_price': self.total_price,
            'advance_paid': self.advance_paid,
            'assigned_to': self.assigned_to,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_type = db.Column(db.String(30), default='partial')
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'amount': self.amount,
            'payment_type': self.payment_type,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    currency = db.Column(db.String(10), default='KES')
    category = db.Column(db.String(80))
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(20), default='in')
    method = db.Column(db.String(20), default='cash')
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'currency': self.currency,
            'category': self.category,
            'amount': self.amount,
            'transaction_type': self.transaction_type,
            'method': self.method,
            'transaction_date': self.transaction_date.isoformat() if self.transaction_date else None,
            'details': self.details,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Swap(db.Model):
    __tablename__ = 'swaps'
    id = db.Column(db.Integer, primary_key=True)
    from_account = db.Column(db.String(20), default='KES')
    to_account = db.Column(db.String(20), default='USD')
    from_cash_amount = db.Column(db.Float, default=0)
    from_digital_amount = db.Column(db.Float, default=0)
    to_cash_amount = db.Column(db.Float, default=0)
    to_digital_amount = db.Column(db.Float, default=0)
    exchange_rate = db.Column(db.Float)
    details = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'from_account': self.from_account,
            'to_account': self.to_account,
            'from_cash_amount': self.from_cash_amount,
            'from_digital_amount': self.from_digital_amount,
            'to_cash_amount': self.to_cash_amount,
            'to_digital_amount': self.to_digital_amount,
            'exchange_rate': self.exchange_rate,
            'details': self.details,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Bank(db.Model):
    __tablename__ = 'banks'
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    balance = db.Column(db.Float, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'account_number': self.account_number,
            'name': self.name,
            'balance': self.balance,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column(db.Integer, primary_key=True)
    item_type = db.Column(db.String(60), default='fabric')
    name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Float, default=0)
    unit = db.Column(db.String(20), default='pcs')
    min_stock = db.Column(db.Float)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'item_type': self.item_type,
            'name': self.name,
            'quantity': self.quantity,
            'unit': self.unit,
            'min_stock': self.min_stock,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(30), default='assigned')
    progress_notes = db.Column(db.Text)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    order = db.relationship('Order', backref='tasks')

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'assigned_to': self.assigned_to,
            'status': self.status,
            'progress_notes': self.progress_notes,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class LowStockAlertRead(db.Model):
    __tablename__ = 'low_stock_alert_reads'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    recipient_type = db.Column(db.String(20))
    recipient_id = db.Column(db.Integer)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    order_id = db.Column(db.Integer)
    type = db.Column(db.String(30))
    message = db.Column(db.Text)
    sent_sms = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)