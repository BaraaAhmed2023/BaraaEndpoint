from flask import Blueprint, request, jsonify, g, current_app
import uuid
from datetime import datetime
from ..middleware import auth_middleware, error_handler
from ..schemas import QuestionCreateSchema, QuestionUpdateSchema, PaginationSchema, AnswerCreateSchema
from ..models import get_db

questions_bp = Blueprint('questions', __name__)

# Get all questions with pagination (public)
@questions_bp.route('/', methods=['GET'])
@error_handler
def get_questions():
    try:
        schema = PaginationSchema()
        data = schema.load(request.args)
        
        page = data['page']
        limit = data['limit']
        
        db = get_db()
        cursor = db.cursor()
        
        offset = (page - 1) * limit
        
        # Get total count
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("SELECT COUNT(*) as total FROM questions")
        else:
            cursor.execute("SELECT COUNT(*) as total FROM questions")
        
        count_result = cursor.fetchone()
        total = count_result[0] if count_result else 0
        
        # Get questions with author info
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT q.*, u.username as author_username 
                FROM questions q
                LEFT JOIN users u ON q.author_id = u.id
                ORDER BY q.created_at DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
        else:
            cursor.execute("""
                SELECT q.*, u.username as author_username 
                FROM questions q
                LEFT JOIN users u ON q.author_id = u.id
                ORDER BY q.created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
        
        questions_result = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dicts
        questions = []
        for question in questions_result:
            if hasattr(question, '_asdict'):
                questions.append(question._asdict())
            elif not isinstance(question, dict):
                questions.append(dict(zip([col[0] for col in cursor.description], question)))
            else:
                questions.append(question)
        
        return jsonify({
            'success': True,
            'data': questions,
            'meta': {
                'total': total,
                'page': page,
                'limit': limit,
                'pages': (total + limit - 1) // limit
            }
        })
        
    except Exception as error:
        print(f'Get questions error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب الأسئلة"
        }), 500

# Create answer (authenticated)
@questions_bp.route('/<string:id>/answers', methods=['POST'])
@auth_middleware
@error_handler
def create_answer(id):
    try:
        schema = AnswerCreateSchema()
        data = schema.load(request.json)
        
        user = g.user
        question_id = id
        db = get_db()
        cursor = db.cursor()
        
        answer_id = f"answer-{uuid.uuid4()}"
        now = datetime.utcnow()
        
        # Insert answer into answers table
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                INSERT INTO answers (id, question_id, author_id, body, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (answer_id, question_id, user['id'], data['body'], now, now))
        else:
            cursor.execute("""
                INSERT INTO answers (id, question_id, author_id, body, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (answer_id, question_id, user['id'], data['body'], now, now))
        
        db.commit()
        
        # Return the created answer with author info
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT a.*, u.username AS author_username
                FROM answers a
                LEFT JOIN users u ON a.author_id = u.id
                WHERE a.id = %s
            """, (answer_id,))
        else:
            cursor.execute("""
                SELECT a.*, u.username AS author_username
                FROM answers a
                LEFT JOIN users u ON a.author_id = u.id
                WHERE a.id = ?
            """, (answer_id,))
        
        answer = cursor.fetchone()
        cursor.close()
        
        # Convert to dict
        if hasattr(answer, '_asdict'):
            answer_dict = answer._asdict()
        elif not isinstance(answer, dict):
            answer_dict = dict(zip([col[0] for col in cursor.description], answer))
        else:
            answer_dict = answer
        
        return jsonify({
            'success': True,
            'message': "تم إضافة الإجابة بنجاح",
            'data': answer_dict
        }), 201
        
    except Exception as error:
        print(f'Create answer error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء إضافة الإجابة"
        }), 500

# Get single question with answers (public)
@questions_bp.route('/<string:id>', methods=['GET'])
@error_handler
def get_question(id):
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get question with author info
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT q.*, u.username as author_username 
                FROM questions q
                LEFT JOIN users u ON q.author_id = u.id
                WHERE q.id = %s
            """, (id,))
        else:
            cursor.execute("""
                SELECT q.*, u.username as author_username 
                FROM questions q
                LEFT JOIN users u ON q.author_id = u.id
                WHERE q.id = ?
            """, (id,))
        
        question = cursor.fetchone()
        
        if not question:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "السؤال غير موجود"
            }), 404
        
        # Convert to dict
        if hasattr(question, '_asdict'):
            question_dict = question._asdict()
        elif not isinstance(question, dict):
            question_dict = dict(zip([col[0] for col in cursor.description], question))
        else:
            question_dict = question
        
        # Get answers for this question
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT a.*, u.username as author_username 
                FROM answers a
                LEFT JOIN users u ON a.author_id = u.id
                WHERE a.question_id = %s
                ORDER BY a.created_at ASC
            """, (id,))
        else:
            cursor.execute("""
                SELECT a.*, u.username as author_username 
                FROM answers a
                LEFT JOIN users u ON a.author_id = u.id
                WHERE a.question_id = ?
                ORDER BY a.created_at ASC
            """, (id,))
        
        answers_result = cursor.fetchall()
        cursor.close()
        
        # Convert answers to list of dicts
        answers = []
        for answer in answers_result:
            if hasattr(answer, '_asdict'):
                answers.append(answer._asdict())
            elif not isinstance(answer, dict):
                answers.append(dict(zip([col[0] for col in cursor.description], answer)))
            else:
                answers.append(answer)
        
        return jsonify({
            'success': True,
            'data': {
                **question_dict,
                'answers': answers,
                'answers_count': len(answers)
            }
        })
        
    except Exception as error:
        print(f'Get question error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب السؤال"
        }), 500

# Create question (authenticated)
@questions_bp.route('/', methods=['POST'])
@auth_middleware
@error_handler
def create_question():
    try:
        schema = QuestionCreateSchema()
        data = schema.load(request.json)
        
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        question_id = f"question-{uuid.uuid4()}"
        now = datetime.utcnow()
        
        # Insert question
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                INSERT INTO questions (
                    id, author_id, title, body, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                question_id,
                user['id'],
                data['title'],
                data.get('body', ''),
                now,
                now
            ))
        else:
            cursor.execute("""
                INSERT INTO questions (
                    id, author_id, title, body, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                question_id,
                user['id'],
                data['title'],
                data.get('body', ''),
                now,
                now
            ))
        
        db.commit()
        
        # Get created question with author info
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT q.*, u.username as author_username 
                FROM questions q
                LEFT JOIN users u ON q.author_id = u.id
                WHERE q.id = %s
            """, (question_id,))
        else:
            cursor.execute("""
                SELECT q.*, u.username as author_username 
                FROM questions q
                LEFT JOIN users u ON q.author_id = u.id
                WHERE q.id = ?
            """, (question_id,))
        
        question = cursor.fetchone()
        cursor.close()
        
        # Convert to dict
        if hasattr(question, '_asdict'):
            question_dict = question._asdict()
        elif not isinstance(question, dict):
            question_dict = dict(zip([col[0] for col in cursor.description], question))
        else:
            question_dict = question
        
        return jsonify({
            'success': True,
            'message': "تم إنشاء السؤال بنجاح",
            'data': question_dict
        }), 201
        
    except Exception as error:
        print(f'Create question error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء إنشاء السؤال"
        }), 500

# Update question (authenticated - author only)
@questions_bp.route('/<string:id>', methods=['PUT'])
@auth_middleware
@error_handler
def update_question(id):
    try:
        schema = QuestionUpdateSchema()
        data = schema.load(request.json)
        
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        # Check if question exists and belongs to user
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT id FROM questions WHERE id = %s AND author_id = %s",
                (id, user['id'])
            )
        else:
            cursor.execute(
                "SELECT id FROM questions WHERE id = ? AND author_id = ?",
                (id, user['id'])
            )
        
        existing = cursor.fetchone()
        
        if not existing:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "السؤال غير موجود أو ليس لديك صلاحية التعديل عليه"
            }), 404
        
        # Build update query
        updates = []
        values = []
        
        if 'title' in data:
            updates.append("title = %s")
            values.append(data['title'])
        
        if 'body' in data:
            updates.append("body = %s")
            values.append(data['body'])
        
        if not updates:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "لا توجد بيانات للتحديث"
            }), 400
        
        updates.append("updated_at = %s")
        values.append(datetime.utcnow())
        values.extend([id, user['id']])
        
        # Build SQL query
        query = f"UPDATE questions SET {', '.join(updates)} WHERE id = %s AND author_id = %s"
        
        if not current_app.config['DATABASE_URL'].startswith('postgresql://'):
            query = query.replace('%s', '?')
        
        cursor.execute(query, values)
        db.commit()
        
        # Get updated question
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT * FROM questions WHERE id = %s",
                (id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM questions WHERE id = ?",
                (id,)
            )
        
        updated_question = cursor.fetchone()
        cursor.close()
        
        # Convert to dict
        if hasattr(updated_question, '_asdict'):
            question_dict = updated_question._asdict()
        elif not isinstance(updated_question, dict):
            question_dict = dict(zip([col[0] for col in cursor.description], updated_question))
        else:
            question_dict = updated_question
        
        return jsonify({
            'success': True,
            'message': "تم تحديث السؤال بنجاح",
            'data': question_dict
        })
        
    except Exception as error:
        print(f'Update question error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء تحديث السؤال"
        }), 500

# Delete question (authenticated - author only)
@questions_bp.route('/<string:id>', methods=['DELETE'])
@auth_middleware
@error_handler
def delete_question(id):
    try:
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        # Check if question exists and belongs to user
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT id FROM questions WHERE id = %s AND author_id = %s",
                (id, user['id'])
            )
        else:
            cursor.execute(
                "SELECT id FROM questions WHERE id = ? AND author_id = ?",
                (id, user['id'])
            )
        
        existing = cursor.fetchone()
        
        if not existing:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "السؤال غير موجود أو ليس لديك صلاحية الحذف"
            }), 404
        
        # Delete answers first
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "DELETE FROM answers WHERE question_id = %s",
                (id,)
            )
        else:
            cursor.execute(
                "DELETE FROM answers WHERE question_id = ?",
                (id,)
            )
        
        # Delete question
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "DELETE FROM questions WHERE id = %s AND author_id = %s",
                (id, user['id'])
            )
        else:
            cursor.execute(
                "DELETE FROM questions WHERE id = ? AND author_id = ?",
                (id, user['id'])
            )
        
        db.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': "تم حذف السؤال بنجاح"
        })
        
    except Exception as error:
        print(f'Delete question error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء حذف السؤال"
        }), 500

# Get user's questions
@questions_bp.route('/user/my-questions', methods=['GET'])
@auth_middleware
@error_handler
def get_user_questions():
    try:
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT q.*, 
                    (SELECT COUNT(*) FROM answers a WHERE a.question_id = q.id) as answers_count
                FROM questions q
                WHERE q.author_id = %s
                ORDER BY q.created_at DESC
            """, (user['id'],))
        else:
            cursor.execute("""
                SELECT q.*, 
                    (SELECT COUNT(*) FROM answers a WHERE a.question_id = q.id) as answers_count
                FROM questions q
                WHERE q.author_id = ?
                ORDER BY q.created_at DESC
            """, (user['id'],))
        
        questions_result = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dicts
        questions = []
        for question in questions_result:
            if hasattr(question, '_asdict'):
                questions.append(question._asdict())
            elif not isinstance(question, dict):
                questions.append(dict(zip([col[0] for col in cursor.description], question)))
            else:
                questions.append(question)
        
        return jsonify({
            'success': True,
            'data': questions,
            'count': len(questions)
        })
        
    except Exception as error:
        print(f'Get user questions error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب أسئلتك"
        }), 500