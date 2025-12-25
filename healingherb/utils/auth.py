import bcrypt
import jwt
from datetime import datetime, timedelta
import secrets
import string
from flask import current_app
import hashlib

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def generate_token(user: dict) -> dict:
    """Generate JWT tokens"""
    access_payload = {
        'userId': user['id'],
        'username': user['username'],
        'email': user['email'],
        'tokenType': 'access',
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(minutes=15)
    }
    
    refresh_payload = {
        'userId': user['id'],
        'username': user['username'],
        'email': user['email'],
        'tokenType': 'refresh',
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(days=7)
    }
    
    access_token = jwt.encode(
        access_payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256'
    )
    
    refresh_token = jwt.encode(
        refresh_payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm='HS256'
    )
    
    expires_at = int((datetime.utcnow() + timedelta(minutes=15)).timestamp())
    
    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expiresAt': expires_at
    }

def verify_token(token: str) -> dict:
    """Verify JWT token"""
    try:
        payload = jwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=['HS256']
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise Exception('التوكن منتهي الصلاحية')
    except jwt.InvalidTokenError:
        raise Exception('التوكن غير صالح')

def generate_random_string(length: int = 32) -> str:
    """Generate random string for tokens"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_verification_token() -> str:
    """Generate email verification token"""
    return generate_random_string(32)

def generate_reset_token() -> str:
    """Generate password reset token"""
    return generate_random_string(32)

def generate_ticket_code() -> str:
    """Generate AI chat ticket code"""
    return f'TICKET-{generate_random_string(8).upper()}'