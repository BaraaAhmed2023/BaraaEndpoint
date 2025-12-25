from functools import wraps
from flask import request, jsonify, g, current_app
import jwt
import time
from datetime import datetime
from .models import get_db

def auth_middleware(f):
    """JWT Authentication Middleware"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'error': 'مطلوب توكن للمصادقة'
            }), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            payload = jwt.decode(
                token, 
                current_app.config['JWT_SECRET_KEY'], 
                algorithms=['HS256']
            )
            
            if 'userId' not in payload:
                return jsonify({
                    'success': False,
                    'error': 'التوكن غير صالح'
                }), 401
            
            # Get user from database
            db = get_db()
            cursor = db.cursor()
            
            if current_app.config['DATABASE_URL'].startswith('postgresql://'):
                cursor.execute(
                    "SELECT id, username, email, first_name, last_name, is_email_verified FROM users WHERE id = %s",
                    (payload['userId'],)
                )
            else:
                cursor.execute(
                    "SELECT id, username, email, first_name, last_name, is_email_verified FROM users WHERE id = ?",
                    (payload['userId'],)
                )
            
            user = cursor.fetchone()
            cursor.close()
            
            if not user:
                return jsonify({
                    'success': False,
                    'error': 'المستخدم غير موجود'
                }), 401
            
            # Convert to dict if needed
            if hasattr(user, '_asdict'):
                user = user._asdict()
            elif not isinstance(user, dict):
                user = dict(zip([col[0] for col in cursor.description], user))
            
            g.user = user
            g.jwt_payload = payload
            
        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'error': 'التوكن منتهي الصلاحية'
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                'success': False,
                'error': 'التوكن غير صالح'
            }), 401
        except Exception as e:
            print(f'Auth error: {e}')
            return jsonify({
                'success': False,
                'error': 'حدث خطأ في المصادقة'
            }), 500
        
        return f(*args, **kwargs)
    
    return decorated_function

def admin_middleware(f):
    """Admin-only middleware"""
    @wraps(f)
    @auth_middleware
    def decorated_function(*args, **kwargs):
        # Add admin check logic here
        # For now, allowing any authenticated user
        return f(*args, **kwargs)
    
    return decorated_function

def error_handler(f):
    """Global error handler"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            print(f'Error in {f.__name__}: {e}')
            
            # Handle specific errors
            if 'validation' in str(e).lower():
                return jsonify({
                    'success': False,
                    'error': 'بيانات غير صالحة'
                }), 400
            
            if 'not found' in str(e).lower():
                return jsonify({
                    'success': False,
                    'error': 'البيانات المطلوبة غير موجودة'
                }), 404
            
            # Default error
            return jsonify({
                'success': False,
                'error': 'حدث خطأ في الخادم'
            }), 500
    
    return decorated_function

def logging_middleware(f):
    """Request logging middleware"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        response = f(*args, **kwargs)
        duration = time.time() - start_time
        
        print(f'{request.method} {request.path} - {response.status_code} ({duration:.2f}s)')
        return response
    
    return decorated_function