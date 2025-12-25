from flask import Blueprint, request, jsonify, g, current_app
import uuid
from datetime import datetime
from ..middleware import auth_middleware, error_handler
from ..schemas import (
    RegisterSchema, LoginSchema, ResetPasswordSchema,
    ResetPasswordConfirmSchema, ProfileUpdateSchema,
    ChangePasswordSchema
)
from ..utils.auth import (
    hash_password, verify_password, generate_token,
    generate_verification_token, generate_reset_token
)
from ..models import get_db

auth_bp = Blueprint('auth', __name__)

# Register
@auth_bp.route('/register', methods=['POST'])
@error_handler
def register():
    try:
        schema = RegisterSchema()
        data = schema.load(request.json)
        
        db = get_db()
        cursor = db.cursor()
        
        # Check if user exists
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT id FROM users WHERE email = %s OR username = %s",
                (data['email'], data['username'])
            )
        else:
            cursor.execute(
                "SELECT id FROM users WHERE email = ? OR username = ?",
                (data['email'], data['username'])
            )
        
        existing_user = cursor.fetchone()
        
        if existing_user:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "اسم المستخدم أو البريد الإلكتروني موجود مسبقاً"
            }), 409
        
        # Hash password
        password_hash = hash_password(data['password'])
        user_id = f"ur-{uuid.uuid4()}"
        verification_token = generate_verification_token()
        now = datetime.utcnow()
        
        # Insert user
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                INSERT INTO users (
                    id, first_name, last_name, username, email, password_hash,
                    age, height, weight, gender, diseases, allergies, medications,
                    email_verification_token, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                data['first_name'],
                data['last_name'],
                data['username'],
                data['email'],
                password_hash,
                data.get('age'),
                data.get('height'),
                data.get('weight'),
                data.get('gender'),
                data.get('diseases'),
                data.get('allergies'),
                data.get('medications'),
                verification_token,
                now,
                now
            ))
        else:
            cursor.execute("""
                INSERT INTO users (
                    id, first_name, last_name, username, email, password_hash,
                    age, height, weight, gender, diseases, allergies, medications,
                    email_verification_token, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                data['first_name'],
                data['last_name'],
                data['username'],
                data['email'],
                password_hash,
                data.get('age'),
                data.get('height'),
                data.get('weight'),
                data.get('gender'),
                data.get('diseases'),
                data.get('allergies'),
                data.get('medications'),
                verification_token,
                now,
                now
            ))
        
        # Generate token
        tokens = generate_token({
            'id': user_id,
            'username': data['username'],
            'email': data['email']
        })
        
        # Store refresh token in database (hashed)
        refresh_token_hash = hash_password(tokens['refresh_token'])
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at) 
                VALUES (%s, %s, %s, %s)
            """, (
                str(uuid.uuid4()),
                user_id,
                refresh_token_hash,
                datetime.utcfromtimestamp(tokens['expiresAt'])
            ))
        else:
            cursor.execute("""
                INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at) 
                VALUES (?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                user_id,
                refresh_token_hash,
                datetime.utcfromtimestamp(tokens['expiresAt'])
            ))
        
        db.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': "تم إنشاء الحساب بنجاح.",
            'data': {
                'id': user_id,
                'username': data['username'],
                'email': data['email'],
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token'],
                'expiresAt': tokens['expiresAt']
            }
        }), 201
        
    except Exception as error:
        print(f'Register error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء إنشاء الحساب"
        }), 500

# Login
@auth_bp.route('/login', methods=['POST'])
@error_handler
def login():
    try:
        schema = LoginSchema()
        data = schema.load(request.json)
        
        db = get_db()
        cursor = db.cursor()
        
        # Get user with password hash
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT id, username, email, password_hash, is_email_verified 
                FROM users WHERE username = %s OR email = %s
            """, (data['username'], data['username']))
        else:
            cursor.execute("""
                SELECT id, username, email, password_hash, is_email_verified 
                FROM users WHERE username = ? OR email = ?
            """, (data['username'], data['username']))
        
        user_result = cursor.fetchone()
        
        if not user_result:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "اسم المستخدم أو كلمة المرور غير صحيحة"
            }), 401
        
        # Convert to dict
        if hasattr(user_result, '_asdict'):
            user = user_result._asdict()
        elif not isinstance(user_result, dict):
            user = dict(zip([col[0] for col in cursor.description], user_result))
        else:
            user = user_result
        
        # Verify password
        if not verify_password(data['password'], user['password_hash']):
            cursor.close()
            return jsonify({
                'success': False,
                'error': "اسم المستخدم أو كلمة المرور غير صحيحة"
            }), 401
        
        # Check email verification (optional)
        # if not user['is_email_verified']:
        #     return jsonify({
        #         'success': False,
        #         'error': "يرجى تفعيل بريدك الإلكتروني أولاً",
        #         'requires_verification': True
        #     }), 403
        
        # Generate token
        tokens = generate_token({
            'id': user['id'],
            'username': user['username'],
            'email': user['email']
        })
        
        # Store refresh token in database (hashed)
        refresh_token_hash = hash_password(tokens['refresh_token'])
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at) 
                VALUES (%s, %s, %s, %s)
            """, (
                str(uuid.uuid4()),
                user['id'],
                refresh_token_hash,
                datetime.utcfromtimestamp(tokens['expiresAt'])
            ))
        else:
            cursor.execute("""
                INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at) 
                VALUES (?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                user['id'],
                refresh_token_hash,
                datetime.utcfromtimestamp(tokens['expiresAt'])
            ))
        
        db.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': "تم تسجيل الدخول بنجاح",
            'data': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token'],
                'expiresAt': tokens['expiresAt']
            }
        })
        
    except Exception as error:
        print(f'Login error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء تسجيل الدخول"
        }), 500

# Get current user profile (protected)
@auth_bp.route('/me', methods=['GET'])
@auth_middleware
@error_handler
def get_profile():
    try:
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT id, first_name, last_name, username, email, 
                       age, height, weight, gender, diseases, 
                       allergies, medications, created_at, updated_at 
                FROM users WHERE id = %s
            """, (user['id'],))
        else:
            cursor.execute("""
                SELECT id, first_name, last_name, username, email, 
                       age, height, weight, gender, diseases, 
                       allergies, medications, created_at, updated_at 
                FROM users WHERE id = ?
            """, (user['id'],))
        
        user_profile = cursor.fetchone()
        cursor.close()
        
        if hasattr(user_profile, '_asdict'):
            user_profile = user_profile._asdict()
        elif not isinstance(user_profile, dict):
            user_profile = dict(zip([col[0] for col in cursor.description], user_profile))
        
        return jsonify({
            'success': True,
            'data': user_profile
        })
        
    except Exception as error:
        print(f'Get profile error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب الملف الشخصي"
        }), 500

# Update profile (protected)
@auth_bp.route('/me', methods=['PUT'])
@auth_middleware
@error_handler
def update_profile():
    try:
        schema = ProfileUpdateSchema()
        data = schema.load(request.json)
        
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        # Build update query
        updates = []
        values = []
        
        fields_map = {
            'first_name': 'first_name',
            'last_name': 'last_name',
            'age': 'age',
            'height': 'height',
            'weight': 'weight',
            'gender': 'gender',
            'diseases': 'diseases',
            'allergies': 'allergies',
            'medications': 'medications'
        }
        
        for field, db_field in fields_map.items():
            if field in data and data[field] is not None:
                updates.append(f"{db_field} = %s")
                values.append(data[field])
        
        if not updates:
            return jsonify({
                'success': False,
                'error': "لا توجد بيانات للتحديث"
            }), 400
        
        updates.append("updated_at = %s")
        values.append(datetime.utcnow())
        values.append(user['id'])
        
        # Build SQL query
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
        
        if not current_app.config['DATABASE_URL'].startswith('postgresql://'):
            query = query.replace('%s', '?')
        
        cursor.execute(query, values)
        db.commit()
        
        # Get updated user
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT id, first_name, last_name, username, email, 
                       age, height, weight, gender, diseases, 
                       allergies, medications, created_at, updated_at 
                FROM users WHERE id = %s
            """, (user['id'],))
        else:
            cursor.execute("""
                SELECT id, first_name, last_name, username, email, 
                       age, height, weight, gender, diseases, 
                       allergies, medications, created_at, updated_at 
                FROM users WHERE id = ?
            """, (user['id'],))
        
        updated_user = cursor.fetchone()
        cursor.close()
        
        if hasattr(updated_user, '_asdict'):
            updated_user = updated_user._asdict()
        elif not isinstance(updated_user, dict):
            updated_user = dict(zip([col[0] for col in cursor.description], updated_user))
        
        return jsonify({
            'success': True,
            'message': "تم تحديث الملف الشخصي بنجاح",
            'data': updated_user
        })
        
    except Exception as error:
        print(f'Update profile error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء تحديث الملف الشخصي"
        }), 500

# Change password (protected)
@auth_bp.route('/change-password', methods=['POST'])
@auth_middleware
@error_handler
def change_password():
    try:
        schema = ChangePasswordSchema()
        data = schema.load(request.json)
        
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        # Get current password hash
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT password_hash FROM users WHERE id = %s",
                (user['id'],)
            )
        else:
            cursor.execute(
                "SELECT password_hash FROM users WHERE id = ?",
                (user['id'],)
            )
        
        current_user = cursor.fetchone()
        
        if not current_user:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "المستخدم غير موجود"
            }), 404
        
        current_hash = current_user[0]
        
        # Verify current password
        if not verify_password(data['currentPassword'], current_hash):
            cursor.close()
            return jsonify({
                'success': False,
                'error': "كلمة المرور الحالية غير صحيحة"
            }), 401
        
        # Hash new password
        new_password_hash = hash_password(data['newPassword'])
        
        # Update password
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s",
                (new_password_hash, datetime.utcnow(), user['id'])
            )
        else:
            cursor.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (new_password_hash, datetime.utcnow(), user['id'])
            )
        
        db.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': "تم تغيير كلمة المرور بنجاح"
        })
        
    except Exception as error:
        print(f'Change password error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء تغيير كلمة المرور"
        }), 500

# Reset password request
@auth_bp.route('/reset-password', methods=['POST'])
@error_handler
def reset_password():
    try:
        schema = ResetPasswordSchema()
        data = schema.load(request.json)
        
        email = data['email']
        db = get_db()
        cursor = db.cursor()
        
        # Check if user exists
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT id FROM users WHERE email = %s",
                (email,)
            )
        else:
            cursor.execute(
                "SELECT id FROM users WHERE email = ?",
                (email,)
            )
        
        user = cursor.fetchone()
        
        if not user:
            # Don't reveal that user doesn't exist
            cursor.close()
            return jsonify({
                'success': True,
                'message': "إذا كان البريد الإلكتروني مسجلاً، ستستلم رابط إعادة تعيين كلمة المرور"
            })
        
        user_id = user[0]
        
        # Generate reset token
        reset_token = generate_reset_token()
        expiry = datetime.utcnow().timestamp() + 3600  # 1 hour
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                UPDATE users SET reset_password_token = %s, reset_token_expiry = %s WHERE id = %s
            """, (reset_token, expiry, user_id))
        else:
            cursor.execute("""
                UPDATE users SET reset_password_token = ?, reset_token_expiry = ? WHERE id = ?
            """, (reset_token, expiry, user_id))
        
        db.commit()
        cursor.close()
        
        # TODO: Send reset password email
        print(f"Reset token for {email}: {reset_token}")
        
        return jsonify({
            'success': True,
            'message': "إذا كان البريد الإلكتروني مسجلاً، ستستلم رابط إعادة تعيين كلمة المرور"
        })
        
    except Exception as error:
        print(f'Reset password error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء طلب إعادة تعيين كلمة المرور"
        }), 500

# Reset password confirm
@auth_bp.route('/reset-password-confirm', methods=['POST'])
@error_handler
def reset_password_confirm():
    try:
        schema = ResetPasswordConfirmSchema()
        data = schema.load(request.json)
        
        token = data['token']
        new_password = data['newPassword']
        
        db = get_db()
        cursor = db.cursor()
        
        # Find user with valid reset token
        now = datetime.utcnow().timestamp()
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT id FROM users WHERE reset_password_token = %s AND reset_token_expiry > %s
            """, (token, now))
        else:
            cursor.execute("""
                SELECT id FROM users WHERE reset_password_token = ? AND reset_token_expiry > ?
            """, (token, now))
        
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "رابط إعادة التعيين غير صالح أو منتهي الصلاحية"
            }), 400
        
        user_id = user[0]
        
        # Hash new password
        new_password_hash = hash_password(new_password)
        
        # Update password and clear reset token
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                UPDATE users SET 
                    password_hash = %s, 
                    reset_password_token = NULL, 
                    reset_token_expiry = NULL,
                    updated_at = %s
                WHERE id = %s
            """, (new_password_hash, datetime.utcnow(), user_id))
        else:
            cursor.execute("""
                UPDATE users SET 
                    password_hash = ?, 
                    reset_password_token = NULL, 
                    reset_token_expiry = NULL,
                    updated_at = ?
                WHERE id = ?
            """, (new_password_hash, datetime.utcnow(), user_id))
        
        db.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': "تم إعادة تعيين كلمة المرور بنجاح"
        })
        
    except Exception as error:
        print(f'Reset password confirm error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء إعادة تعيين كلمة المرور"
        }), 500

# Logout (client-side only)
@auth_bp.route('/logout', methods=['POST'])
@auth_middleware
@error_handler
def logout():
    return jsonify({
        'success': True,
        'message': "تم تسجيل الخروج بنجاح"
    })