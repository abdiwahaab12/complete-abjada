import secrets
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt
from extensions import db
from models import User

auth_bp = Blueprint('auth', __name__)
ROLES = ('admin', 'tailor', 'cashier')

def role_required(*allowed):
    def decorator(fn):
        from flask_jwt_extended import verify_jwt_in_request
        from functools import wraps
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('role') not in allowed and 'admin' not in allowed:
                return jsonify({'error': 'Insufficient role'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login endpoint - requires email and password, connects to MySQL database"""
    try:
        data = request.get_json() or {}
        email = (data.get('email') or '').strip().lower()
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        # Query user from database by email
        user = User.query.filter(User.email == email).first()
        
        if not user:
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Check password using bcrypt
        if not user.check_password(password):
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Check if user is active
        if not user.is_active:
            return jsonify({'error': 'Account disabled'}), 403
        
        # Create JWT tokens
        access = create_access_token(
            identity=user.id,
            additional_claims={'role': user.role, 'username': user.username}
        )
        refresh = create_refresh_token(identity=user.id)
        
        return jsonify({
            'access_token': access,
            'refresh_token': refresh,
            'user': user.to_dict()
        })
    except Exception as e:
        # Log error for debugging
        print(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed. Please try again.'}), 500

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    try:
        uid = get_jwt_identity()
        user = User.query.get(uid)
        if not user or not user.is_active:
            return jsonify({'error': 'Invalid token'}), 401
        access = create_access_token(
            identity=user.id,
            additional_claims={'role': user.role, 'username': user.username}
        )
        return jsonify({'access_token': access})
    except Exception as e:
        return jsonify({'error': 'Token refresh failed'}), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    """Get current user info"""
    try:
        uid = get_jwt_identity()
        user = User.query.get(uid)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        return jsonify(user.to_dict())
    except Exception as e:
        return jsonify({'error': 'Failed to get user info'}), 500

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password"""
    try:
        uid = get_jwt_identity()
        user = User.query.get(uid)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        data = request.get_json() or {}
        current = data.get('current_password')
        new_pass = data.get('new_password')
        if not current or not new_pass:
            return jsonify({'error': 'Current and new password required'}), 400
        if not user.check_password(current):
            return jsonify({'error': 'Current password is wrong'}), 400
        user.set_password(new_pass)
        db.session.commit()
        return jsonify({'message': 'Password updated'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update password'}), 500

@auth_bp.route('/request-reset', methods=['POST'])
def request_reset():
    """Request password reset token"""
    try:
        data = request.get_json() or {}
        email = data.get('email')
        if not email:
            return jsonify({'error': 'Email required'}), 400
        user = User.query.filter_by(email=email.lower().strip()).first()
        if user:
            user.reset_token = secrets.token_urlsafe(32)
            user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            # In production: send email with link containing reset_token
        return jsonify({'message': 'If the email exists, a reset link was sent'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to process reset request'}), 500

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Reset password using token"""
    try:
        data = request.get_json() or {}
        token = data.get('token')
        new_password = data.get('new_password')
        if not token or not new_password:
            return jsonify({'error': 'Token and new password required'}), 400
        user = User.query.filter_by(reset_token=token).first()
        if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
            return jsonify({'error': 'Invalid or expired token'}), 400
        user.set_password(new_password)
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()
        return jsonify({'message': 'Password reset successful'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to reset password'}), 500

@auth_bp.route('/users', methods=['GET'])
@jwt_required()
def list_users():
    """List users for dropdowns (e.g. Bank User)."""
    users = User.query.filter(User.is_active == True).order_by(User.full_name).all()
    return jsonify([{'id': u.id, 'username': u.username, 'full_name': u.full_name or u.username} for u in users])


@auth_bp.route('/staff', methods=['GET'])
@jwt_required()
def list_staff():
    """List all staff members (admin only)"""
    try:
        claims = get_jwt()
        if claims.get('role') != 'admin':
            return jsonify({'error': 'Admin only'}), 403
        staff = User.query.filter(User.role.in_(ROLES)).all()
        return jsonify([u.to_dict() for u in staff])
    except Exception as e:
        return jsonify({'error': 'Failed to fetch staff'}), 500

@auth_bp.route('/staff', methods=['POST'])
@jwt_required()
def create_staff():
    """Create new staff member (admin only)"""
    try:
        claims = get_jwt()
        if claims.get('role') != 'admin':
            return jsonify({'error': 'Admin only'}), 403
        data = request.get_json() or {}
        username = data.get('username')
        email = (data.get('email') or '').strip().lower()
        password = data.get('password')
        role = (data.get('role') or 'tailor').lower()
        if role not in ROLES:
            role = 'tailor'
        if not username or not email or not password:
            return jsonify({'error': 'Username, email and password required'}), 400
        if User.query.filter((User.username == username) | (User.email == email)).first():
            return jsonify({'error': 'Username or email already exists'}), 400
        user = User(username=username, email=email, role=role, full_name=data.get('full_name'), is_active=True)
        user.set_password(password)
        user.phone = data.get('phone')
        db.session.add(user)
        db.session.commit()
        return jsonify(user.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create staff member'}), 500
