import requests
import json
from flask import current_app
from datetime import datetime
import uuid
from .auth import generate_random_string

class AIRateLimiter:
    """Rate limiter for AI requests"""
    def __init__(self):
        self.requests = {}
        self.limit = 60
        self.window_minutes = 15
    
    def check(self, user_id: str) -> dict:
        """Check if user is rate limited"""
        now = datetime.utcnow()
        key = f"ai:{user_id}"
        
        if key not in self.requests:
            self.requests[key] = {
                'count': 1,
                'window_start': now,
                'reset_time': now.timestamp() + (self.window_minutes * 60)
            }
            return {
                'allowed': True,
                'remaining': self.limit - 1,
                'resetAfter': self.window_minutes * 60 * 1000
            }
        
        user_data = self.requests[key]
        
        # Reset if window has passed
        window_end = user_data['window_start'].timestamp() + (self.window_minutes * 60)
        if now.timestamp() > window_end:
            user_data['count'] = 1
            user_data['window_start'] = now
            user_data['reset_time'] = now.timestamp() + (self.window_minutes * 60)
            return {
                'allowed': True,
                'remaining': self.limit - 1,
                'resetAfter': self.window_minutes * 60 * 1000
            }
        
        if user_data['count'] >= self.limit:
            return {
                'allowed': False,
                'remaining': 0,
                'resetAfter': int((user_data['reset_time'] - now.timestamp()) * 1000)
            }
        
        user_data['count'] += 1
        return {
            'allowed': True,
            'remaining': self.limit - user_data['count'],
            'resetAfter': int((user_data['reset_time'] - now.timestamp()) * 1000)
        }
    
    def get_headers(self, user_id: str) -> dict:
        """Get rate limit headers"""
        key = f"ai:{user_id}"
        if key not in self.requests:
            return {}
        
        user_data = self.requests[key]
        return {
            'X-RateLimit-Limit': str(self.limit),
            'X-RateLimit-Remaining': str(self.limit - user_data['count']),
            'X-RateLimit-Reset': str(int(user_data['reset_time']))
        }

# Global rate limiter instance

def sanitize_message(message: str) -> str:
    """Sanitize AI chat message"""
    if not message:
        return ""
    
    # Remove harmful characters but keep Arabic
    sanitized = message.strip()
    sanitized = sanitized[:5000]  # Limit length
    
    return sanitized

def check_emergency_keywords(message: str) -> bool:
    """Check for emergency keywords in Arabic"""
    emergency_keywords = [
        'طارئ', 'إسعاف', 'مستعجل', 'خطير', 'مخيف', 'نزيف',
        'ألم شديد', 'صعوبة تنفس', 'فقدان وعي', 'حادث', 'سكتة',
        'نوبة قلبية', 'تسمم', 'حرق', 'غرق', 'اختناق'
    ]
    
    message_lower = message.lower()
    for keyword in emergency_keywords:
        if keyword in message_lower:
            return True
    
    return False

def create_system_prompt(profile: dict) -> str:
    """Create system prompt for AI based on user profile"""
    prompt = """أنت مساعد طبي عربي متخصص تسمى "عشبة شفاء". مهمتك تقديم معلومات طبية عامة ونصائح صحية.

المعلومات التي يجب مراعاتها:
- أنا مريض سكري وأتابع حالتي
- لدي حساسية من بعض الأدوية
- أتناول أدوية منتظمة

قواعد مهمة:
1. لا تقدم تشخيصات طبية نهائية
2. لا تصف أدوية محددة بجرعات
3. شجع دائمًا على استشارة الطبيب
4. في الحالات الطارئة، نبه المريض للاتصال بالطوارئ
5. استخدم اللغة العربية الفصحى مع بعض التعبيرات الدارجة
6. كن داعمًا ومتفهمًا
7. قدم معلومات دقيقة وموثوقة
8. إذا لم تكن متأكدًا، قل "لا أعرف" بدلاً من التخمين

ملاحظة: المعلومات المقدمة هي للاسترشاد فقط وليست بديلاً عن الاستشارة الطبية."""

    # Add user-specific information
    if profile:
        if profile.get('diseases'):
            prompt += f"\n\nالأمراض المزمنة للمستخدم: {profile['diseases']}"
        if profile.get('allergies'):
            prompt += f"\nالحساسية: {profile['allergies']}"
        if profile.get('medications'):
            prompt += f"\nالأدوية التي يتناولها: {profile['medications']}"
        if profile.get('age'):
            prompt += f"\nالعمر: {profile['age']}"
        if profile.get('gender'):
            gender_ar = 'ذكر' if profile['gender'] == 'male' else 'أنثى'
            prompt += f"\nالنوع: {gender_ar}"
    
    return prompt

def call_gemini_api(messages: list, model: str = None, temperature: float = 0.7) -> dict:
    """Call Google Gemini API"""
    api_key = current_app.config.get('GEMINI_API_KEY')
    model = model or current_app.config.get('GEMINI_MODEL', 'gemini-2.5-flash')
    
    if not api_key:
        raise Exception('GEMINI_API_KEY غير مضبوط')
    
    # Format messages for Gemini
    contents = []
    for msg in messages:
        if msg['role'] == 'system':
            # System messages go in the first content
            if not contents:
                contents.append({
                    'parts': [{'text': msg['content']}]
                })
            else:
                contents[0]['parts'][0]['text'] = msg['content'] + '\n\n' + contents[0]['parts'][0]['text']
        else:
            contents.append({
                'role': 'user' if msg['role'] == 'user' else 'model',
                'parts': [{'text': msg['content']}]
            })
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    data = {
        'contents': contents,
        'generationConfig': {
            'temperature': temperature,
            'maxOutputTokens': current_app.config.get('AI_MAX_TOKENS', 1000),
            'topP': 0.95,
            'topK': 40
        },
        'safetySettings': [
            {
                'category': 'HARM_CATEGORY_HARASSMENT',
                'threshold': 'BLOCK_MEDIUM_AND_ABOVE'
            },
            {
                'category': 'HARM_CATEGORY_HATE_SPEECH',
                'threshold': 'BLOCK_MEDIUM_AND_ABOVE'
            },
            {
                'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT',
                'threshold': 'BLOCK_MEDIUM_AND_ABOVE'
            },
            {
                'category': 'HARM_CATEGORY_DANGEROUS_CONTENT',
                'threshold': 'BLOCK_MEDIUM_AND_ABOVE'
            }
        ]
    }
    
    try:
        response = requests.post(
            url,
            headers={'Content-Type': 'application/json'},
            data=json.dumps(data),
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f'API Error: {response.status_code}')
        
        result = response.json()
        
        if 'candidates' in result and result['candidates']:
            ai_response = result['candidates'][0]['content']['parts'][0]['text']
            
            # Calculate approximate tokens
            input_tokens = sum(len(msg['content'].split()) for msg in messages)
            output_tokens = len(ai_response.split())
            total_tokens = input_tokens + output_tokens
            
            return {
                'response': ai_response,
                'usage': {
                    'total_tokens': total_tokens,
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens
                }
            }
        else:
            raise Exception('لا توجد استجابة من API')
            
    except requests.exceptions.Timeout:
        raise Exception('انتهت مهلة الاتصال بالـ API')
    except Exception as e:
        raise Exception(f'خطأ في استدعاء الـ API: {str(e)}')

def get_fallback_response(message: str, is_emergency: bool) -> str:
    """Get fallback response when API fails"""
    if is_emergency:
        return """🚨 **ملاحظة مهمة**: يبدو أن رسالتك تحتوي على كلمات طارئة.

💡 **تذكير عاجل**: 
- للحالات الطارئة، يرجى الاتصال بالطوارئ على الرقم 123
- توجه لأقرب مستشفى أو مركز طوارئ
- لا تنتظر الرد في الحالات الحرجة

⚠️ **نظام المساعدة الطبية غير متوفر حاليًا**. 
يرجى استخدام قنوات الطوارئ الرسمية للحصول على المساعدة الفورية."""

    return """مرحبًا! 👋

عذرًا، نظام المساعدة الطبية غير متوفر حاليًا. 

💡 **نصائح عامة**:
1. للحالات الطارئة: اتصل بالطوارئ على 123
2. للمواعيد: راجع طبيبك الخاص
3. للتساؤلات العامة: يمكنك البحث في قسم الأسئلة الشائعة

🔧 **حاول مرة أخرى لاحقًا**، أو:
- استخدم ميزة البحث في التطبيق
- راجع مكتبة المعلومات الصحية
- تحقق من قسم الوصفات والنصائح

نعتذر للإزعاج ونعمل على حل المشكلة."""