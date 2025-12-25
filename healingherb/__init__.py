from flask import Blueprint, jsonify, request, current_app, g
from datetime import datetime
import time
import uuid

# Create the main blueprint
healingherb_bp = Blueprint('healingherb', __name__)

# Rate limiting storage
rate_limits = {}

# Apply middleware to all routes
@healingherb_bp.before_request
def before_request():
    # Start timer for request duration
    g.start_time = time.time()
    
    # Rate limiting
    ip = request.remote_addr
    window_ms = 15 * 60 * 1000  # 15 minutes
    limit = 100  # requests per window
    now = time.time() * 1000  # Convert to milliseconds
    window_start = now - window_ms
    
    # Clean old entries
    for key in list(rate_limits.keys()):
        if rate_limits[key]['reset_time'] < window_start:
            del rate_limits[key]
    
    if ip not in rate_limits:
        rate_limits[ip] = {'count': 1, 'reset_time': now}
    else:
        if rate_limits[ip]['count'] >= limit:
            return jsonify({
                'success': False,
                'error': 'لقد تجاوزت الحد المسموح به من الطلبات. يرجى المحاولة مرة أخرى لاحقًا.'
            }), 429
        rate_limits[ip]['count'] += 1
    
    # Add rate limit headers
    from flask import make_response
    if hasattr(g, 'response'):
        g.response.headers['X-RateLimit-Limit'] = str(limit)
        g.response.headers['X-RateLimit-Remaining'] = str(limit - rate_limits[ip]['count'])
        g.response.headers['X-RateLimit-Reset'] = str(int(rate_limits[ip]['reset_time'] + window_ms))

@healingherb_bp.after_request
def after_request(response):
    # Log request duration
    if hasattr(g, 'start_time'):
        duration = time.time() - g.start_time
        print(f"{request.method} {request.path} - {response.status_code} ({duration:.2f}s)")
    
    # CORS headers
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    
    return response

@healingherb_bp.route('/health')
def health_check():
    return jsonify({
        "success": True,
        "status": "healthy",
        "service": "Healing Herb API",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    })

@healingherb_bp.route('/')
def heal_index():
    data = {
        "success": True,
        "message": "🌿 عشبة شفاء API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "auth": "/apis/healing-herbs/auth",
            "appointments": "/apis/healing-herbs/appointments",
            "daily-stats": "/apis/healing-herbs/daily-stats",
            "herbs": "/apis/healing-herbs/herbs",
            "medical-tests": "/apis/healing-herbs/medical-tests",
            "questions": "/apis/healing-herbs/questions",
            "recipes": "/apis/healing-herbs/recipes",
            "recipe-ratings": "/apis/healing-herbs/recipe-ratings",
            "reports": "/apis/healing-herbs/reports",
            "ai": "/apis/healing-herbs/ai",
            "health": "/apis/healing-herbs/health"
        },
        "documentation": "مرحباً بكم في API عشبة شفاء. استخدم التوكن للمصادقة على الطلبات المحمية."
    }
    return jsonify(data)

@healingherb_bp.route('/test-db')
def test_db():
    try:
        from .models import get_db
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()
        cursor.close()
        return jsonify({
            "success": True,
            "database": "connected",
            "version": db_version[0] if db_version else "unknown"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "database": "disconnected",
            "error": str(e)
        }), 500

# Import all route blueprints
from .routes.auth import auth_bp
from .routes.appointments import appointments_bp
from .routes.daily_stats import daily_stats_bp
from .routes.herbs import herbs_bp
from .routes.medical_tests import medical_tests_bp
from .routes.questions import questions_bp
from .routes.recipes import recipes_bp
from .routes.recipe_ratings import recipe_ratings_bp
from .routes.reports import reports_bp
from .routes.ai import ai_bp

# Register all blueprints with their URL prefixes
healingherb_bp.register_blueprint(auth_bp, url_prefix='/auth')
healingherb_bp.register_blueprint(appointments_bp, url_prefix='/appointments')
healingherb_bp.register_blueprint(daily_stats_bp, url_prefix='/daily-stats')
healingherb_bp.register_blueprint(herbs_bp, url_prefix='/herbs')
healingherb_bp.register_blueprint(medical_tests_bp, url_prefix='/medical-tests')
healingherb_bp.register_blueprint(questions_bp, url_prefix='/questions')
healingherb_bp.register_blueprint(recipes_bp, url_prefix='/recipes')
healingherb_bp.register_blueprint(recipe_ratings_bp, url_prefix='/recipe-ratings')
healingherb_bp.register_blueprint(reports_bp, url_prefix='/reports')
healingherb_bp.register_blueprint(ai_bp, url_prefix='/ai')

# Export the main blueprint
__all__ = ['healingherb_bp']