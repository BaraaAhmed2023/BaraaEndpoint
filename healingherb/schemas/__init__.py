from marshmallow import Schema, fields, validate, validates, ValidationError
from datetime import datetime

# ==================== COMMON SCHEMAS ====================
class PaginationSchema(Schema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    limit = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))
    sort = fields.String(load_default='created_at')
    order = fields.String(load_default='desc', validate=validate.OneOf(['asc', 'desc']))

class SearchQuerySchema(Schema):
    q = fields.String()
    search = fields.String()
    limit = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))
    offset = fields.Integer(load_default=0, validate=validate.Range(min=0))

# ==================== AUTH SCHEMAS ====================
class RegisterSchema(Schema):
    first_name = fields.String(required=True, validate=validate.Length(min=1))
    last_name = fields.String(required=True, validate=validate.Length(min=1))
    username = fields.String(required=True, validate=validate.Length(min=3))
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=8))
    age = fields.Integer(allow_none=True, validate=validate.Range(min=1, max=150))
    height = fields.Float(allow_none=True, validate=validate.Range(min=50, max=250))
    weight = fields.Float(allow_none=True, validate=validate.Range(min=10, max=300))
    gender = fields.String(allow_none=True, validate=validate.OneOf(['male', 'female', 'ذكر', 'انثى']))
    diseases = fields.String(allow_none=True)
    allergies = fields.String(allow_none=True)
    medications = fields.String(allow_none=True)
    
    @validates('password')
    def validate_password(self, value):
        if not any(c.isupper() for c in value):
            raise ValidationError('كلمة المرور يجب أن تحتوي على حرف كبير واحد على الأقل')
        if not any(c.islower() for c in value):
            raise ValidationError('كلمة المرور يجب أن تحتوي على حرف صغير واحد على الأقل')
        if not any(c.isdigit() for c in value):
            raise ValidationError('كلمة المرور يجب أن تحتوي على رقم واحد على الأقل')

class LoginSchema(Schema):
    username = fields.String(required=True)
    password = fields.String(required=True)

class ResetPasswordSchema(Schema):
    email = fields.Email(required=True)

class ResetPasswordConfirmSchema(Schema):
    token = fields.String(required=True)
    newPassword = fields.String(required=True, validate=validate.Length(min=8))

class ProfileUpdateSchema(Schema):
    first_name = fields.String()
    last_name = fields.String()
    age = fields.Integer(allow_none=True, validate=validate.Range(min=1, max=150))
    height = fields.Float(allow_none=True, validate=validate.Range(min=50, max=250))
    weight = fields.Float(allow_none=True, validate=validate.Range(min=10, max=300))
    gender = fields.String(allow_none=True, validate=validate.OneOf(['male', 'female']))
    diseases = fields.String(allow_none=True)
    allergies = fields.String(allow_none=True)
    medications = fields.String(allow_none=True)

class VerifyEmailSchema(Schema):
    token = fields.String(required=True)

class ResendVerificationSchema(Schema):
    email = fields.Email(required=True)

class ChangePasswordSchema(Schema):
    currentPassword = fields.String(required=True)
    newPassword = fields.String(required=True, validate=validate.Length(min=8))

# ==================== APPOINTMENT SCHEMAS ====================
class AppointmentBaseSchema(Schema):
    name = fields.String()
    date = fields.String(required=True, validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'))
    time = fields.String(required=True, validate=validate.Regexp(r'^\d{2}:\d{2}(:\d{2})?$'))
    location = fields.String(required=True, validate=validate.Length(min=1))
    appointment_type = fields.String(load_default='regular', validate=validate.OneOf([
        'medical', 'regular', 'follow-up', 'emergency', 'annual',
        'consultation', 'diagnostic', 'procedure', 'second_opinion',
        'telemedicine', 'physical_exam', 'group_session', 'home_visit', 'virtual'
    ]))
    notes_or_details = fields.String(allow_none=True)

class AppointmentCreateSchema(AppointmentBaseSchema):
    @validates('date')
    def validate_future_date(self, value):
        try:
            appointment_date = datetime.strptime(value, '%Y-%m-%d')
            if appointment_date.date() < datetime.utcnow().date():
                raise ValidationError('لا يمكن إنشاء موعد بتاريخ سابق')
        except ValueError:
            raise ValidationError('صيغة التاريخ غير صحيحة')

class AppointmentUpdateSchema(AppointmentBaseSchema):
    pass

# ==================== DAILY STATS SCHEMAS ====================
class DailyStatCreateSchema(Schema):
    date = fields.String(validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'))
    sugar_level = fields.Float(required=True, validate=validate.Range(min=0, max=1000))
    blood_pressure_systolic = fields.Integer(required=True, validate=validate.Range(min=50, max=250))
    blood_pressure_diastolic = fields.Integer(required=True, validate=validate.Range(min=30, max=150))
    notes = fields.String(allow_none=True)

# ==================== HERB SCHEMAS ====================
class HerbCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    description = fields.String(required=True)
    uses = fields.String(required=True)
    benefits = fields.String(allow_none=True)
    harms = fields.String(allow_none=True)
    image_url = fields.URL(allow_none=True)

class HerbUpdateSchema(HerbCreateSchema):
    pass

class HerbStoryCreateSchema(Schema):
    title = fields.String(required=True, validate=validate.Length(min=1, max=70))
    herb_id = fields.String(required=True, validate=validate.Regexp(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'))
    short_description = fields.String(required=True, validate=validate.Length(min=1, max=120))
    story = fields.String(required=True)
    image_url = fields.URL(allow_none=True)

class HerbStoryUpdateSchema(HerbStoryCreateSchema):
    pass

# ==================== MEDICAL TEST SCHEMAS ====================
class MedicalTestCreateSchema(Schema):
    date = fields.String(required=True, validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'))
    time = fields.String(validate=validate.Regexp(r'^\d{2}:\d{2}(:\d{2})?$'))
    title = fields.String(required=True, validate=validate.Length(min=1, max=255))
    subtitle = fields.String(validate=validate.Length(max=255))
    result = fields.String(required=True)
    notes = fields.String(load_default='')

class MedicalTestUpdateSchema(MedicalTestCreateSchema):
    pass

# ==================== QUESTION SCHEMAS ====================
class QuestionCreateSchema(Schema):
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    body = fields.String(load_default='')

class QuestionUpdateSchema(QuestionCreateSchema):
    pass

class AnswerCreateSchema(Schema):
    body = fields.String(required=True, validate=validate.Length(min=1))

class AnswerUpdateSchema(AnswerCreateSchema):
    pass

# ==================== RECIPE SCHEMAS ====================
class RecipeCreateSchema(Schema):
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    description = fields.String(validate=validate.Length(max=500))
    ingredients = fields.String()
    instructions = fields.String()

class RecipeUpdateSchema(RecipeCreateSchema):
    pass

class RecipeRatingSchema(Schema):
    rating = fields.Integer(required=True, validate=validate.Range(min=0, max=5))

# ==================== AI CHAT SCHEMAS ====================
class ChatSchema(Schema):
    message = fields.String(required=True, validate=validate.Length(min=1, max=5000))
    model = fields.String(load_default='gemini-2.5-flash')
    temperature = fields.Float(load_default=0.7, validate=validate.Range(min=0.1, max=2.0))
    stream = fields.Boolean(load_default=False)

class ChatHistorySchema(Schema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    limit = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))
    search = fields.String()
    start_date = fields.DateTime(allow_none=True)
    end_date = fields.DateTime(allow_none=True)
    sort_by = fields.String(load_default='created_at', validate=validate.OneOf(['created_at', 'tokens_used']))
    sort_order = fields.String(load_default='desc', validate=validate.OneOf(['asc', 'desc']))

class ClearHistorySchema(Schema):
    confirm = fields.Boolean(load_default=False)
    older_than_days = fields.Integer(allow_none=True, validate=validate.Range(min=1, max=365))

class AIFeedbackSchema(Schema):
    message_id = fields.String(required=True, validate=validate.Regexp(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'))
    rating = fields.Integer(required=True, validate=validate.Range(min=1, max=5))
    feedback = fields.String(validate=validate.Length(max=500))
    helpful = fields.Boolean()

# ==================== REPORT SCHEMAS ====================
class CreateReportSchema(Schema):
    title = fields.String(validate=validate.Length(max=200))
    include_recipes = fields.Boolean(load_default=False)
    include_stats = fields.Boolean(load_default=True)
    include_tests = fields.Boolean(load_default=True)
    include_appointments = fields.Boolean(load_default=True)