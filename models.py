import secrets
from datetime import datetime, timedelta
from extensions import db, bcrypt


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