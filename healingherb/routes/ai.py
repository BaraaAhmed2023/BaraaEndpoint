from flask import Blueprint, request, jsonify, g, current_app
import uuid
from datetime import datetime
from ..middleware import auth_middleware, error_handler
from ..schemas import (
    ChatSchema, ChatHistorySchema, ClearHistorySchema, 
    AIFeedbackSchema, PaginationSchema
)
from ..utils.ai_utils import (
    AIRateLimiter, sanitize_message, check_emergency_keywords,
    create_system_prompt, call_gemini_api, get_fallback_response
)
from ..models import get_db
import json
ai_rate_limiter = AIRateLimiter()
ai_bp = Blueprint('ai', __name__)

# Apply middleware
@ai_bp.before_request
def before_request():
    pass

# AI Chat endpoint - MAIN ENDPOINT
@ai_bp.route('/chat', methods=['POST'])
@auth_middleware
@error_handler
def chat():
    try:
        # Validate input
        schema = ChatSchema()
        data = schema.load(request.json)
        
        user = g.user
        message = data['message']
        model = data['model']
        temperature = data['temperature']
        
        db = get_db()
        cursor = db.cursor()
        
        # Rate limiting check
        rate_limit = ai_rate_limiter.check(user['id'])
        if not rate_limit['allowed']:
            return jsonify({
                'success': False,
                'error': f'لقد تجاوزت الحد المسموح به من الطلبات. يرجى المحاولة بعد {int(rate_limit["resetAfter"] / 60000)} دقائق.'
            }), 429
        
        # Add rate limit headers
        rate_headers = ai_rate_limiter.get_headers(user['id'])
        
        # Sanitize and validate message
        sanitized_message = sanitize_message(message)
        if not sanitized_message:
            return jsonify({
                'success': False,
                'error': "الرسالة لا يمكن أن تكون فارغة"
            }), 400
        
        # Check for emergency keywords
        is_emergency = check_emergency_keywords(sanitized_message)
        
        # Get user profile for context
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT * FROM users WHERE id = %s",
                (user['id'],)
            )
        else:
            cursor.execute(
                "SELECT * FROM users WHERE id = ?",
                (user['id'],)
            )
        
        profile = cursor.fetchone()
        if not profile:
            return jsonify({
                'success': False,
                'error': "المستخدم غير موجود"
            }), 404
        
        # Get recent conversation context (last 3 pairs)
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT message, response, created_at 
                FROM ai_chat_messages 
                WHERE user_id = %s 
                ORDER BY created_at DESC 
                LIMIT 6
            """, (user['id'],))
        else:
            cursor.execute("""
                SELECT message, response, created_at 
                FROM ai_chat_messages 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT 6
            """, (user['id'],))
        
        context_messages = cursor.fetchall()
        context = []
        
        # Reverse to get chronological order
        for msg in reversed(context_messages):
            if hasattr(msg, '_asdict'):
                msg = msg._asdict()
            elif not isinstance(msg, dict):
                msg = dict(zip([col[0] for col in cursor.description], msg))
            
            context.append({
                'role': 'user',
                'content': msg['message']
            })
            context.append({
                'role': 'assistant',
                'content': msg['response']
            })
        
        # Prepare messages for AI
        messages = [
            {
                'role': 'system',
                'content': create_system_prompt(profile)
            },
            *context,
            {
                'role': 'user',
                'content': sanitized_message
            }
        ]
        
        ai_response = ""
        tokens_used = 0
        
        try:
            # Call Gemini API
            result = call_gemini_api(messages, model, temperature)
            
            ai_response = result['response']
            tokens_used = result['usage']['total_tokens']
            
            # Add emergency warning if needed
            if is_emergency and '🚨' not in ai_response and 'طارئ' not in ai_response:
                ai_response = f"""🚨 **ملاحظة مهمة**: يبدو أن رسالتك تحتوي على كلمات طارئة.

{ai_response}

💡 **تذكير**: للحالات الطارئة، يرجى الاتصال بالطوارئ على 123 أو التوجه لأقرب مستشفى."""
                
        except Exception as api_error:
            print(f'AI API error: {api_error}')
            
            # Use fallback response
            ai_response = get_fallback_response(sanitized_message, is_emergency)
            tokens_used = len(sanitized_message.split()) + len(ai_response.split())
        
        # Save chat message to database
        message_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Save user message
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                INSERT INTO ai_chat_messages (id, user_id, message, response, model, tokens_used, is_user, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (message_id, user['id'], sanitized_message, ai_response, model, tokens_used, True, now))
        else:
            cursor.execute("""
                INSERT INTO ai_chat_messages (id, user_id, message, response, model, tokens_used, is_user, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (message_id, user['id'], sanitized_message, ai_response, model, tokens_used, True, now))
        
        db.commit()
        
        response_data = {
            'success': True,
            'data': {
                'response': ai_response,
                'message_id': message_id,
                'tokens_used': tokens_used,
                'model': model,
                'timestamp': now.isoformat(),
                'is_emergency': is_emergency
            },
            'meta': {
                'rate_limit': {
                    'remaining': rate_limit['remaining'],
                    'reset_after': int(rate_limit['resetAfter'] / 1000)  # seconds
                }
            }
        }
        
        response = jsonify(response_data)
        
        # Add rate limit headers
        for key, value in rate_headers.items():
            response.headers[key] = str(value)
        
        return response
        
    except Exception as error:
        print(f'Chat error: {error}')
        return jsonify({
            'success': False,
            'error': str(error) or "حدث خطأ أثناء معالجة رسالتك. يرجى المحاولة مرة أخرى."
        }), 500
    finally:
        cursor.close()

@ai_bp.route('/chat', methods=['GET'])
def chat_get():
    return jsonify({
        'success': False,
        'error': "الطلب غير متاح" 
    }), 400

# Get chat history
@ai_bp.route('/history', methods=['GET'])
@auth_middleware
@error_handler
def get_history():
    try:
        schema = ChatHistorySchema()
        data = schema.load(request.args)
        
        user = g.user
        page = data['page']
        limit = data['limit']
        search = data.get('search')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        sort_by = data['sort_by']
        sort_order = data['sort_order']
        
        db = get_db()
        cursor = db.cursor()
        
        offset = (page - 1) * limit
        
        # Build query
        query = "SELECT * FROM ai_chat_messages WHERE user_id = %s"
        params = [user['id']]
        
        if search:
            query += " AND (message LIKE %s OR response LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])
        
        if start_date:
            query += " AND created_at >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND created_at <= %s"
            params.append(end_date)
        
        # Order by
        order_by = 'tokens_used' if sort_by == 'tokens_used' else 'created_at'
        query += f" ORDER BY {order_by} {sort_order.upper()} LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        messages_result = cursor.fetchall()
        
        # Get total count
        count_query = "SELECT COUNT(*) as total FROM ai_chat_messages WHERE user_id = %s"
        count_params = [user['id']]
        
        if search:
            count_query += " AND (message LIKE %s OR response LIKE %s)"
            count_params.extend([f"%{search}%", f"%{search}%"])
        
        if start_date:
            count_query += " AND created_at >= %s"
            count_params.append(start_date)
        
        if end_date:
            count_query += " AND created_at <= %s"
            count_params.append(end_date)
        
        cursor.execute(count_query, count_params)
        count_result = cursor.fetchone()
        total = count_result[0] if count_result else 0
        
        # Group messages by conversation
        conversations = []
        messages = []
        
        for msg in messages_result:
            if hasattr(msg, '_asdict'):
                msg = msg._asdict()
            elif not isinstance(msg, dict):
                msg = dict(zip([col[0] for col in cursor.description], msg))
            messages.append(msg)
        
        for i in range(0, len(messages), 2):
            user_msg = messages[i] if i < len(messages) else None
            ai_msg = messages[i + 1] if i + 1 < len(messages) else None
            
            if user_msg and user_msg.get('is_user'):
                conversations.append({
                    'id': str(uuid.uuid4()),
                    'user_message': user_msg,
                    'ai_response': ai_msg,
                    'timestamp': user_msg.get('created_at'),
                    'tokens_used': (user_msg.get('tokens_used') or 0) + (ai_msg.get('tokens_used') or 0)
                })
        
        cursor.close()
        
        return jsonify({
            'success': True,
            'data': {
                'conversations': conversations,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'pages': (total + limit - 1) // limit
                }
            }
        })
        
    except Exception as error:
        print(f'Get chat history error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب سجل المحادثة"
        }), 500

# Clear chat history
@ai_bp.route('/history', methods=['DELETE'])
@auth_middleware
@error_handler
def clear_history():
    try:
        schema = ClearHistorySchema()
        data = schema.load(request.json)
        
        user = g.user
        confirm = data['confirm']
        older_than_days = data.get('older_than_days')
        
        if not confirm:
            return jsonify({
                'success': False,
                'error': "يرجى التأكيد على رغبتك في مسح سجل المحادثة"
            }), 400
        
        db = get_db()
        cursor = db.cursor()
        
        query = "DELETE FROM ai_chat_messages WHERE user_id = %s"
        params = [user['id']]
        
        if older_than_days:
            from datetime import datetime, timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
            query += " AND created_at < %s"
            params.append(cutoff_date)
        
        cursor.execute(query, params)
        deleted_count = cursor.rowcount
        
        db.commit()
        cursor.close()
        
        message = (f"تم مسح المحادثات الأقدم من {older_than_days} يوم" 
                   if older_than_days else "تم مسح سجل المحادثة بالكامل")
        
        return jsonify({
            'success': True,
            'message': message,
            'data': {
                'deleted_count': deleted_count
            }
        })
        
    except Exception as error:
        print(f'Clear history error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء مسح سجل المحادثة"
        }), 500

# Get AI usage statistics
@ai_bp.route('/stats', methods=['GET'])
@auth_middleware
@error_handler
def get_stats():
    try:
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        # Get total messages and tokens
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT COUNT(*) as total_messages, COALESCE(SUM(tokens_used), 0) as total_tokens 
                FROM ai_chat_messages 
                WHERE user_id = %s
            """, (user['id'],))
        else:
            cursor.execute("""
                SELECT COUNT(*) as total_messages, COALESCE(SUM(tokens_used), 0) as total_tokens 
                FROM ai_chat_messages 
                WHERE user_id = ?
            """, (user['id'],))
        
        stats = cursor.fetchone()
        
        # Get today's usage
        today = datetime.utcnow().date()
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT COUNT(*) as today_messages, COALESCE(SUM(tokens_used), 0) as today_tokens 
                FROM ai_chat_messages 
                WHERE user_id = %s AND DATE(created_at) = %s
            """, (user['id'], today))
        else:
            cursor.execute("""
                SELECT COUNT(*) as today_messages, COALESCE(SUM(tokens_used), 0) as today_tokens 
                FROM ai_chat_messages 
                WHERE user_id = ? AND DATE(created_at) = ?
            """, (user['id'], today))
        
        today_stats = cursor.fetchone()
        
        cursor.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_messages': stats[0] if stats else 0,
                'total_tokens': stats[1] if stats else 0,
                'today_messages': today_stats[0] if today_stats else 0,
                'today_tokens': today_stats[1] if today_stats else 0,
                'rate_limit': {
                    'limit': current_app.config.get('AI_RATE_LIMIT', 60),
                    'window_minutes': 15,
                    'description': "60 طلب كل 15 دقيقة"
                }
            }
        })
        
    except Exception as error:
        print(f'Get AI stats error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب إحصائيات الاستخدام"
        }), 500

# Submit feedback for AI response
@ai_bp.route('/feedback', methods=['POST'])
@auth_middleware
@error_handler
def submit_feedback():
    try:
        schema = AIFeedbackSchema()
        data = schema.load(request.json)
        
        user = g.user
        message_id = data['message_id']
        rating = data['rating']
        feedback = data.get('feedback')
        helpful = data.get('helpful', False)
        
        db = get_db()
        cursor = db.cursor()
        
        # Verify message exists and belongs to user
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT id FROM ai_chat_messages WHERE id = %s AND user_id = %s
            """, (message_id, user['id']))
        else:
            cursor.execute("""
                SELECT id FROM ai_chat_messages WHERE id = ? AND user_id = ?
            """, (message_id, user['id']))
        
        message = cursor.fetchone()
        
        if not message:
            return jsonify({
                'success': False,
                'error': "الرسالة غير موجودة أو لا تملك صلاحية الوصول"
            }), 404
        
        feedback_id = str(uuid.uuid4())
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                INSERT INTO ai_feedback (id, user_id, message_id, rating, feedback, helpful) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (feedback_id, user['id'], message_id, rating, feedback, helpful))
        else:
            cursor.execute("""
                INSERT INTO ai_feedback (id, user_id, message_id, rating, feedback, helpful) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (feedback_id, user['id'], message_id, rating, feedback, helpful))
        
        db.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': "شكراً على ملاحظاتك! نسعى دائماً لتحسين خدماتنا.",
            'data': {'feedback_id': feedback_id}
        })
        
    except Exception as error:
        print(f'Submit feedback error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء حفظ الملاحظات"
        }), 500

# Get available AI models
@ai_bp.route('/models', methods=['GET'])
@error_handler
def get_models():
    try:
        models = [
            {
                'id': 'gemini-2.5-flash',
                'name': 'Gemini 2.5 Flash',
                'description': 'نموذج جوجل السريع للمحادثات متعددة اللغات',
                'max_tokens': 32768,
                'languages': ['العربية', 'الإنجليزية'],
                'cost_per_1k_tokens': 0.0005
            },
            {
                'id': 'gemini-2.0-flash',
                'name': 'Gemini 2.0 Flash',
                'description': 'نموذج جوجل السريع للمحادثات العامة',
                'max_tokens': 32768,
                'languages': ['العربية', 'الإنجليزية'],
                'cost_per_1k_tokens': 0.0005
            },
            {
                'id': 'gemini-1.5-pro',
                'name': 'Gemini 1.5 Pro',
                'description': 'نموذج جوجل المتقدم للتحليل المعقد',
                'max_tokens': 32768,
                'languages': ['العربية', 'الإنجليزية'],
                'cost_per_1k_tokens': 0.0015
            }
        ]
        
        return jsonify({
            'success': True,
            'data': {
                'models': models,
                'default_model': current_app.config.get('DEFAULT_AI_MODEL', 'gemini-2.5-flash'),
                'max_tokens_per_request': current_app.config.get('AI_MAX_TOKENS', 1000),
                'recommended_for_medical': 'gemini-1.5-pro'
            }
        })
        
    except Exception as error:
        print(f'Get models error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب النماذج المتاحة"
        }), 500

# Health check for AI service
@ai_bp.route('/health', methods=['GET'])
@auth_middleware
@error_handler
def health_check():
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Test database connection
        cursor.execute("SELECT 1")
        
        # Test Gemini API configuration
        api_key = current_app.config.get('GEMINI_API_KEY')
        is_api_configured = bool(api_key and len(api_key) > 10)
        
        cursor.close()
        
        return jsonify({
            'success': True,
            'data': {
                'service': 'AI Chat Service',
                'status': 'operational',
                'timestamp': datetime.utcnow().isoformat(),
                'components': {
                    'database': 'connected',
                    'gemini_api': 'configured' if is_api_configured else 'not_configured',
                    'rate_limiting': 'active',
                    'default_model': current_app.config.get('DEFAULT_AI_MODEL', 'gemini-2.5-flash')
                },
                'limits': {
                    'max_tokens': current_app.config.get('AI_MAX_TOKENS', 1000),
                    'max_history': current_app.config.get('AI_MAX_HISTORY', 10),
                    'rate_limit': current_app.config.get('AI_RATE_LIMIT', 60)
                }
            }
        })
        
    except Exception as error:
        print(f'AI health check error: {error}')
        return jsonify({
            'success': False,
            'data': {
                'service': 'AI Chat Service',
                'status': 'degraded',
                'error': str(error),
                'timestamp': datetime.utcnow().isoformat()
            }
        }), 500