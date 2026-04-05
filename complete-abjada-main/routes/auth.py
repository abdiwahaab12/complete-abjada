import secrets
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from extensions import db
from models import User
from role_helpers import SUPER_ADMIN_ROLES, STAFF_ROLES, is_super_admin_role

auth_bp = Blueprint('auth', __name__)
# Allowed roles when creating/editing staff (Super Admin only).
ROLES = ('super_admin', 'employee', 'admin', 'tailor', 'cashier')

def role_required(*allowed):
    def decorator(fn):
        from flask_jwt_extended import verify_jwt_in_request
        from functools import wraps
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            r = claims.get('role')
            if r in SUPER_ADMIN_ROLES:
                return fn(*args, **kwargs)
            if r in allowed:
                return fn(*args, **kwargs)
            return jsonify({'error': 'Insufficient role'}), 403
        return wrapper
    return decorator

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login with email or username plus password (JSON: email, password — username/login also accepted)."""
    try:
        data = request.get_json(force=True, silent=True)
        if data is None:
            return jsonify({'error': 'Invalid or empty JSON body'}), 400
        if not isinstance(data, dict):
            data = {}

        raw_id = (
            data.get('email')
            or data.get('username')
            or data.get('login')
            or ''
        )
        identifier = raw_id.strip().lower() if isinstance(raw_id, str) else str(raw_id).strip().lower()

        password = data.get('password')
        if password is not None and not isinstance(password, str):
            password = str(password)

        if not identifier or password is None or password == '':
            return jsonify({'error': 'Email (or username) and password are required'}), 400

        # Match by email, or by username
        user = User.query.filter(func.lower(User.email) == identifier).first()
        if not user:
            user = User.query.filter(func.lower(User.username) == identifier).first()

        if not user:
            return jsonify({'error': 'Invalid email or password'}), 401

        try:
            ok = user.check_password(password)
        except (ValueError, TypeError) as e:
            current_app.logger.warning('Password check failed for user %s: %s', user.id, e)
            ok = False
        if not ok:
            return jsonify({'error': 'Invalid email or password'}), 401

        if not user.is_active:
            return jsonify({'error': 'Account disabled'}), 403

        try:
            ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if ip and ',' in ip:
                ip = ip.split(',')[0].strip()
            user.record_login(ip or request.remote_addr)
            db.session.commit()
        except Exception as ex:
            db.session.rollback()
            current_app.logger.warning('record_login failed: %s', ex)

        access = create_access_token(
            identity=user.id,
            additional_claims={'role': user.role, 'username': user.username},
        )
        refresh = create_refresh_token(identity=user.id)

        return jsonify({
            'access_token': access,
            'refresh_token': refresh,
            'user': user.to_dict(),
        })
    except Exception as e:
        print(f'Login error: {str(e)}')
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
    claims = get_jwt()
    if not is_super_admin_role(claims.get('role')):
        return jsonify({'error': 'Super Admin access required'}), 403
    users = User.query.filter(User.is_active == True).order_by(User.full_name).all()
    return jsonify([{'id': u.id, 'username': u.username, 'full_name': u.full_name or u.username} for u in users])


@auth_bp.route('/staff', methods=['GET'])
@jwt_required()
def list_staff():
    """List all staff members (Super Admin only)"""
    try:
        claims = get_jwt()
        if not is_super_admin_role(claims.get('role')):
            return jsonify({'error': 'Super Admin only'}), 403
        staff = User.query.filter(User.role.in_(STAFF_ROLES)).all()
        return jsonify([u.to_dict() for u in staff])
    except Exception as e:
        return jsonify({'error': 'Failed to fetch staff'}), 500

@auth_bp.route('/staff', methods=['POST'])
@jwt_required()
def create_staff():
    """Create new staff member (Super Admin only)"""
    try:
        claims = get_jwt()
        if not is_super_admin_role(claims.get('role')):
            return jsonify({'error': 'Super Admin only'}), 403
        data = request.get_json() or {}
        username = data.get('username')
        email = (data.get('email') or '').strip().lower()
        password = data.get('password')
        role = (data.get('role') or 'employee').lower()
        if role not in ROLES:
            role = 'employee'
        if role in ('tailor', 'cashier'):
            role = 'employee'
        if role == 'super_admin' and claims.get('role') not in ('super_admin', 'admin'):
            role = 'employee'
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


@auth_bp.route('/staff/<int:uid>', methods=['PUT'])
@jwt_required()
def update_staff(uid):
    """Update staff member (Super Admin only)"""
    try:
        claims = get_jwt()
        if not is_super_admin_role(claims.get('role')):
            return jsonify({'error': 'Super Admin only'}), 403
        user = User.query.get(uid)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        data = request.get_json() or {}

        username = (data.get('username') or user.username or '').strip()
        email = (data.get('email') or user.email or '').strip().lower()
        role = (data.get('role') or user.role or 'employee').lower()
        if role not in ROLES:
            role = 'employee'
        if role in ('tailor', 'cashier'):
            role = 'employee'
        if role == 'super_admin' and claims.get('role') not in ('super_admin', 'admin'):
            role = 'employee'
        if not username or not email:
            return jsonify({'error': 'Username and email required'}), 400

        exists = User.query.filter(User.id != uid).filter((User.username == username) | (User.email == email)).first()
        if exists:
            return jsonify({'error': 'Username or email already exists'}), 400

        user.username = username
        user.email = email
        user.role = role
        user.full_name = (data.get('full_name') if data.get('full_name') is not None else user.full_name)
        user.phone = (data.get('phone') if data.get('phone') is not None else user.phone)

        new_password = (data.get('password') or '').strip()
        if new_password:
            user.set_password(new_password)

        db.session.commit()
        return jsonify(user.to_dict())
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to update staff member'}), 500


@auth_bp.route('/staff/<int:uid>', methods=['DELETE'])
@jwt_required()
def delete_staff(uid):
    """Delete staff member (Super Admin only). Hard-deletes when safe; otherwise deactivates if DB rows still reference this user."""
    claims = get_jwt()
    if not is_super_admin_role(claims.get('role')):
        return jsonify({'error': 'Super Admin only'}), 403
    me = get_jwt_identity()
    if int(me) == int(uid):
        return jsonify({'error': 'You cannot delete your own account'}), 400
    user = User.query.get(uid)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if not user.is_active:
        return jsonify({
            'message': 'This account is already deactivated.',
            'deactivated': True,
            'already_inactive': True,
        })

    admin_roles = ('super_admin', 'admin')
    if user.role in admin_roles:
        others = (
            User.query.filter(
                User.id != uid,
                User.role.in_(admin_roles),
                User.is_active.is_(True),
            ).count()
        )
        if others == 0:
            return jsonify({'error': 'Cannot remove the only active administrator account'}), 400

    def _deactivate_linked_account():
        db.session.rollback()
        u = User.query.get(uid)
        if not u:
            return jsonify({'error': 'User not found'}), 404
        try:
            u.is_active = False
            db.session.commit()
            return jsonify({
                'message': (
                    'Staff member deactivated. Their account is still linked to orders, transactions, '
                    'or other records, so the user row was not removed.'
                ),
                'deactivated': True,
            })
        except Exception:
            db.session.rollback()
            return jsonify({'error': 'Could not deactivate staff member'}), 500

    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({'message': 'Deleted', 'deactivated': False})
    except IntegrityError:
        return _deactivate_linked_account()
    except Exception as e:
        db.session.rollback()
        err = str(e).lower()
        # MySQL InnoDB FK (e.g. 1451) is not always raised as IntegrityError depending on driver
        if (
            'foreign key' in err
            or '1451' in str(e)
            or 'cannot delete or update a parent row' in err
        ):
            return _deactivate_linked_account()
        return jsonify({'error': 'Failed to delete staff member'}), 500
