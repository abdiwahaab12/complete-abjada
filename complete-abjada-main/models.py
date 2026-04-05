import json
import re
import secrets
from datetime import datetime, timedelta
from extensions import db, bcrypt

# Low stock threshold for alert notifications (piece count)
LOW_STOCK_ALERT_THRESHOLD = 5
# Fabric: warn when remaining yards drops below this (tailoring fabric)
LOW_FABRIC_YARDS_THRESHOLD = 3.0


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
        """Legacy + super admin."""
        return self.role in ("admin", "super_admin")

    @property
    def is_super_admin(self):
        return self.role in ("super_admin", "admin")

    @property
    def is_employee(self):
        return self.role in ("employee", "tailor", "cashier")

    @property
    def is_staff(self):
        return self.is_super_admin or self.is_employee

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
    # Tailoring fabric: product-level (legacy) or color variant
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True, index=True)
    product_color_id = db.Column(db.Integer, db.ForeignKey('product_colors.id'), nullable=True, index=True)
    fabric_yards = db.Column(db.Float, nullable=True)
    # JSON object: {"body": 2.0, "sleeve": 1.0, "collar": 0.5} — sum must match fabric_yards
    fabric_yard_breakdown = db.Column(db.Text, nullable=True)
    # Qamis, Shirt, Surwaal, etc.
    clothing_type = db.Column(db.String(80), nullable=True)

    fabric_usage = db.relationship('FabricUsage', backref='measurement', uselist=False)

    def to_dict(self):
        yard_breakdown = None
        if self.fabric_yard_breakdown:
            try:
                yard_breakdown = json.loads(self.fabric_yard_breakdown)
            except Exception:
                yard_breakdown = None
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
            'product_id': self.product_id,
            'product_color_id': self.product_color_id,
            'fabric_yards': self.fabric_yards,
            'yard_breakdown': yard_breakdown,
            'clothing_type': self.clothing_type,
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
    # paid | unpaid | partial — kept in sync with total_price / advance_paid (see finance_logic)
    payment_status = db.Column(db.String(20), default='unpaid')
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    payments = db.relationship('Payment', backref='order', lazy='dynamic', cascade='all, delete-orphan')

    def balance_due(self):
        tp = float(self.total_price or 0)
        ap = float(self.advance_paid or 0)
        return max(0.0, round(tp - ap, 2))

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
            'payment_status': getattr(self, 'payment_status', None) or 'unpaid',
            'balance_due': self.balance_due(),
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
    # Account received | Receivable | Liability — controls financial section routing
    account_type = db.Column(db.String(40))
    # Customer (receivable) or creditor/supplier (liability); optional
    counterparty = db.Column(db.String(200))
    # Optional link to customers table when user picks a customer
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    # For Received / Receivable: amount paid toward this line (esp. partial payments)
    paid_amount = db.Column(db.Float)
    transaction_type = db.Column(db.String(20), default='in')
    method = db.Column(db.String(20), default='cash')
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)
    # Optional: paid | unpaid | partial — for IN entries (cashbook classification)
    payment_status = db.Column(db.String(20))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'currency': self.currency,
            'category': self.category,
            'account_type': self.account_type,
            'counterparty': self.counterparty,
            'customer_id': self.customer_id,
            'amount': self.amount,
            'paid_amount': self.paid_amount,
            'transaction_type': self.transaction_type,
            'method': self.method,
            'transaction_date': self.transaction_date.isoformat() if self.transaction_date else None,
            'details': self.details,
            'payment_status': self.payment_status,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Liability(db.Model):
    """Amounts owed to suppliers / creditors (independent from customer orders)."""
    __tablename__ = 'liabilities'
    id = db.Column(db.Integer, primary_key=True)
    creditor_name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(40))
    amount = db.Column(db.Float, nullable=False)
    paid_amount = db.Column(db.Float, default=0)
    liability_date = db.Column(db.Date)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    def balance(self):
        return max(0.0, round(float(self.amount or 0) - float(self.paid_amount or 0), 2))

    def status_label(self):
        b = self.balance()
        if b <= 0.01:
            return 'paid'
        if float(self.paid_amount or 0) <= 0.01:
            return 'unpaid'
        return 'partial'

    def to_dict(self):
        return {
            'id': self.id,
            'creditor_name': self.creditor_name,
            'phone': self.phone,
            'amount': float(self.amount or 0),
            'paid_amount': float(self.paid_amount or 0),
            'balance': self.balance(),
            'status': self.status_label(),
            'liability_date': self.liability_date.isoformat() if self.liability_date else None,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by,
        }


class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(80), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    expense_date = db.Column(db.Date)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    def to_dict(self):
        return {
            'id': self.id,
            'category': self.category,
            'amount': float(self.amount or 0),
            'expense_date': self.expense_date.isoformat() if self.expense_date else None,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by,
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
            'created_by': self.created_by,
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


class ProductCategory(db.Model):
    __tablename__ = 'product_categories'
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(24), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'public_id': self.public_id,
            'name': self.name,
            'slug': self.slug,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def new_public_id():
        return secrets.token_hex(12)


class TransactionCategory(db.Model):
    __tablename__ = 'transaction_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True, index=True)
    # Simple text field for now; UI shows "All Users" by default.
    allowed_users = db.Column(db.String(80), default='all')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'allowed_users': self.allowed_users,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by,
        }


def _parse_price_from_notes(notes: str | None) -> float | None:
    if not notes:
        return None
    for line in notes.splitlines():
        m = re.match(r'^Price:\s*(.+)$', line.strip(), re.I)
        if m:
            raw = re.sub(r'[^0-9.]', '', m.group(1))
            if not raw:
                return None
            try:
                return float(raw)
            except ValueError:
                return None
    return None


class Inventory(db.Model):
    """Product / stock rows; physical MySQL/SQLite table name is `products`."""
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    item_type = db.Column(db.String(60), default='fabric')
    name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Float, default=0)
    unit = db.Column(db.String(20), default='pcs')
    min_stock = db.Column(db.Float)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Optional: structured fields (price also parsed from notes for legacy rows)
    price = db.Column(db.Float, nullable=True)
    # e.g. fabric family label for color grouping ("Solid", "Printed")
    color_category = db.Column(db.String(120), nullable=True)
    # Default yards per piece when adding new color variants from the product form
    default_yards_per_piece = db.Column(db.Float, nullable=True)
    # Fabric: total purchased / on hand, and remaining after customer deductions
    total_yards = db.Column(db.Float, default=0)
    remaining_yards = db.Column(db.Float, nullable=True)

    color_variants = db.relationship(
        'ProductColor',
        backref='product',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )

    def to_dict(self):
        q = self.quantity or 0
        mn = self.min_stock
        total_y = float(self.total_yards or 0)
        rem_y = self.remaining_yards
        if rem_y is None:
            rem_y = total_y
        else:
            rem_y = float(rem_y)
        low_fabric = total_y > 0 and rem_y < LOW_FABRIC_YARDS_THRESHOLD
        price_val = self.price if self.price is not None else _parse_price_from_notes(self.notes)
        return {
            'id': self.id,
            'item_type': self.item_type,
            'name': self.name,
            'quantity': self.quantity,
            'unit': self.unit,
            'min_stock': self.min_stock,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_low_stock': mn is not None and q <= mn,
            'total_yards': total_y,
            'remaining_yards': rem_y,
            'is_low_fabric': low_fabric,
            'low_fabric_message': 'Stock is running low' if low_fabric else None,
            'price': float(price_val) if price_val is not None else None,
            'color_category': self.color_category,
            'default_yards_per_piece': float(self.default_yards_per_piece)
            if self.default_yards_per_piece is not None
            else None,
        }


class ProductColor(db.Model):
    """
    Per-color fabric stock for a product.
    Total capacity = pieces_quantity * yards_per_piece; remaining_yards is the live pool
    (automatically spans pieces — no manual per-piece rows).
    """
    __tablename__ = 'product_colors'
    __table_args__ = (
        db.UniqueConstraint('product_id', 'color_name', name='uq_product_color_name'),
    )

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    color_name = db.Column(db.String(120), nullable=False)
    pieces_quantity = db.Column(db.Integer, default=0)
    yards_per_piece = db.Column(db.Float, default=0)
    remaining_yards = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def capacity_yards(self) -> float:
        return float(self.pieces_quantity or 0) * float(self.yards_per_piece or 0)

    def effective_remaining_yards(self) -> float:
        if self.remaining_yards is not None:
            return float(self.remaining_yards)
        return self.capacity_yards

    @property
    def used_yards(self) -> float:
        return max(0.0, self.capacity_yards - self.effective_remaining_yards())

    def remaining_pieces_equivalent(self) -> float:
        ypp = float(self.yards_per_piece or 0)
        if ypp <= 0:
            return 0.0
        return self.effective_remaining_yards() / ypp

    def stock_status(self) -> str:
        rem = self.effective_remaining_yards()
        if rem <= 0:
            return 'not_available'
        if rem < LOW_FABRIC_YARDS_THRESHOLD:
            return 'low'
        return 'ok'

    def to_dict(self):
        cap = self.capacity_yards
        rem = self.effective_remaining_yards()
        st = self.stock_status()
        return {
            'id': self.id,
            'product_id': self.product_id,
            'color_name': self.color_name,
            'pieces_quantity': self.pieces_quantity,
            'yards_per_piece': float(self.yards_per_piece or 0),
            'capacity_yards': round(cap, 4),
            'remaining_yards': round(rem, 4),
            'used_yards': round(self.used_yards, 4),
            'remaining_pieces_equivalent': round(self.remaining_pieces_equivalent(), 4),
            'stock_status': st,
            'message': (
                'Not Available' if st == 'not_available' else (
                    'Low stock warning' if st == 'low' else None
                )
            ),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class FabricUsage(db.Model):
    """Audit row: fabric/pieces deducted when a measurement is saved."""
    __tablename__ = 'fabric_usage'
    id = db.Column(db.Integer, primary_key=True)
    measurement_id = db.Column(db.Integer, db.ForeignKey('measurements.id'), nullable=False, unique=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    product_color_id = db.Column(db.Integer, db.ForeignKey('product_colors.id'), nullable=True, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    yards_used = db.Column(db.Float, nullable=False, default=0)
    pieces_deducted = db.Column(db.Float, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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
    inventory_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)


class LowStockColorAlertRead(db.Model):
    """Mark product-color low-stock warnings as read per user."""
    __tablename__ = 'low_stock_color_alert_reads'
    __table_args__ = (db.UniqueConstraint('user_id', 'product_color_id', name='uq_user_color_read'),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_color_id = db.Column(db.Integer, db.ForeignKey('product_colors.id'), nullable=False, index=True)


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