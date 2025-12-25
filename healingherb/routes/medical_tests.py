from flask import Blueprint, request, jsonify, g, current_app
import uuid
from datetime import datetime
from ..middleware import auth_middleware, error_handler
from ..schemas import MedicalTestCreateSchema, MedicalTestUpdateSchema, SearchQuerySchema, PaginationSchema
from ..models import get_db

medical_tests_bp = Blueprint('medical_tests', __name__)

# Get all medical tests with pagination
@medical_tests_bp.route('/', methods=['GET'])
@auth_middleware
@error_handler
def get_medical_tests():
    try:
        schema = PaginationSchema()
        data = schema.load(request.args)
        
        user = g.user
        page = data['page']
        limit = data['limit']
        sort = data.get('sort', 'date')
        order = data.get('order', 'desc')
        
        db = get_db()
        cursor = db.cursor()
        
        offset = (page - 1) * limit
        
        # Get total count
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT COUNT(*) as total FROM medical_tests WHERE user_id = %s",
                (user['id'],)
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) as total FROM medical_tests WHERE user_id = ?",
                (user['id'],)
            )
        
        count_result = cursor.fetchone()
        total = count_result[0] if count_result else 0
        
        # Get tests
        order_clause = f"{sort} {order.upper()}"
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(f"""
                SELECT * FROM medical_tests 
                WHERE user_id = %s 
                ORDER BY {order_clause}
                LIMIT %s OFFSET %s
            """, (user['id'], limit, offset))
        else:
            cursor.execute(f"""
                SELECT * FROM medical_tests 
                WHERE user_id = ? 
                ORDER BY {order_clause}
                LIMIT ? OFFSET ?
            """, (user['id'], limit, offset))
        
        tests_result = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dicts
        tests = []
        for test in tests_result:
            if hasattr(test, '_asdict'):
                tests.append(test._asdict())
            elif not isinstance(test, dict):
                tests.append(dict(zip([col[0] for col in cursor.description], test)))
            else:
                tests.append(test)
        
        return jsonify({
            'success': True,
            'data': tests,
            'meta': {
                'total': total,
                'page': page,
                'limit': limit,
                'pages': (total + limit - 1) // limit,
                'hasNext': page * limit < total,
                'hasPrev': page > 1
            }
        })
        
    except Exception as error:
        print(f'Get medical tests error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب الفحوصات الطبية"
        }), 500

# Get single medical test
@medical_tests_bp.route('/<string:id>', methods=['GET'])
@auth_middleware
@error_handler
def get_medical_test(id):
    try:
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT * FROM medical_tests WHERE id = %s AND user_id = %s",
                (id, user['id'])
            )
        else:
            cursor.execute(
                "SELECT * FROM medical_tests WHERE id = ? AND user_id = ?",
                (id, user['id'])
            )
        
        test = cursor.fetchone()
        cursor.close()
        
        if not test:
            return jsonify({
                'success': False,
                'error': "الفحص الطبي غير موجود أو ليس لديك صلاحية الوصول إليه"
            }), 404
        
        # Convert to dict
        if hasattr(test, '_asdict'):
            test_dict = test._asdict()
        elif not isinstance(test, dict):
            test_dict = dict(zip([col[0] for col in cursor.description], test))
        else:
            test_dict = test
        
        return jsonify({
            'success': True,
            'data': test_dict
        })
        
    except Exception as error:
        print(f'Get medical test error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب الفحص الطبي"
        }), 500

# Create medical test
@medical_tests_bp.route('/', methods=['POST'])
@auth_middleware
@error_handler
def create_medical_test():
    try:
        schema = MedicalTestCreateSchema()
        data = schema.load(request.json)
        
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        test_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Insert test
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                INSERT INTO medical_tests (
                    id, user_id, date, time, title, subtitle, result, notes, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                test_id,
                user['id'],
                data['date'],
                data.get('time'),
                data['title'],
                data.get('subtitle', ''),
                data['result'],
                data.get('notes', ''),
                now
            ))
        else:
            cursor.execute("""
                INSERT INTO medical_tests (
                    id, user_id, date, time, title, subtitle, result, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                test_id,
                user['id'],
                data['date'],
                data.get('time'),
                data['title'],
                data.get('subtitle', ''),
                data['result'],
                data.get('notes', ''),
                now
            ))
        
        db.commit()
        
        # Get created test
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT * FROM medical_tests WHERE id = %s",
                (test_id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM medical_tests WHERE id = ?",
                (test_id,)
            )
        
        test = cursor.fetchone()
        cursor.close()
        
        # Convert to dict
        if hasattr(test, '_asdict'):
            test_dict = test._asdict()
        elif not isinstance(test, dict):
            test_dict = dict(zip([col[0] for col in cursor.description], test))
        else:
            test_dict = test
        
        return jsonify({
            'success': True,
            'message': "تم إضافة الفحص الطبي بنجاح",
            'data': test_dict
        }), 201
        
    except Exception as error:
        print(f'Create medical test error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء إضافة الفحص الطبي"
        }), 500

# Update medical test
@medical_tests_bp.route('/<string:id>', methods=['PUT'])
@auth_middleware
@error_handler
def update_medical_test(id):
    try:
        schema = MedicalTestUpdateSchema()
        data = schema.load(request.json)
        
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        # Check if test exists
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT id FROM medical_tests WHERE id = %s AND user_id = %s",
                (id, user['id'])
            )
        else:
            cursor.execute(
                "SELECT id FROM medical_tests WHERE id = ? AND user_id = ?",
                (id, user['id'])
            )
        
        existing = cursor.fetchone()
        
        if not existing:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "الفحص الطبي غير موجود أو ليس لديك صلاحية التعديل عليه"
            }), 404
        
        # Build update query
        updates = []
        values = []
        
        if 'date' in data:
            updates.append("date = %s")
            values.append(data['date'])
        
        if 'time' in data:
            updates.append("time = %s")
            values.append(data['time'])
        
        if 'title' in data:
            updates.append("title = %s")
            values.append(data['title'])
        
        if 'subtitle' in data:
            updates.append("subtitle = %s")
            values.append(data['subtitle'])
        
        if 'result' in data:
            updates.append("result = %s")
            values.append(data['result'])
        
        if 'notes' in data:
            updates.append("notes = %s")
            values.append(data['notes'])
        
        if not updates:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "لا توجد بيانات للتحديث"
            }), 400
        
        values.extend([id, user['id']])
        
        # Build SQL query
        query = f"UPDATE medical_tests SET {', '.join(updates)} WHERE id = %s AND user_id = %s"
        
        if not current_app.config['DATABASE_URL'].startswith('postgresql://'):
            query = query.replace('%s', '?')
        
        cursor.execute(query, values)
        db.commit()
        
        # Get updated test
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT * FROM medical_tests WHERE id = %s",
                (id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM medical_tests WHERE id = ?",
                (id,)
            )
        
        updated_test = cursor.fetchone()
        cursor.close()
        
        # Convert to dict
        if hasattr(updated_test, '_asdict'):
            test_dict = updated_test._asdict()
        elif not isinstance(updated_test, dict):
            test_dict = dict(zip([col[0] for col in cursor.description], updated_test))
        else:
            test_dict = updated_test
        
        return jsonify({
            'success': True,
            'message': "تم تحديث الفحص الطبي بنجاح",
            'data': test_dict
        })
        
    except Exception as error:
        print(f'Update medical test error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء تحديث الفحص الطبي"
        }), 500

# Delete medical test
@medical_tests_bp.route('/<string:id>', methods=['DELETE'])
@auth_middleware
@error_handler
def delete_medical_test(id):
    try:
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        # Check if test exists
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT id FROM medical_tests WHERE id = %s AND user_id = %s",
                (id, user['id'])
            )
        else:
            cursor.execute(
                "SELECT id FROM medical_tests WHERE id = ? AND user_id = ?",
                (id, user['id'])
            )
        
        existing = cursor.fetchone()
        
        if not existing:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "الفحص الطبي غير موجود أو ليس لديك صلاحية الحذف"
            }), 404
        
        # Delete test
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "DELETE FROM medical_tests WHERE id = %s AND user_id = %s",
                (id, user['id'])
            )
        else:
            cursor.execute(
                "DELETE FROM medical_tests WHERE id = ? AND user_id = ?",
                (id, user['id'])
            )
        
        db.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': "تم حذف الفحص الطبي بنجاح"
        })
        
    except Exception as error:
        print(f'Delete medical test error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء حذف الفحص الطبي"
        }), 500

# Search medical tests
@medical_tests_bp.route('/search', methods=['GET'])
@auth_middleware
@error_handler
def search_medical_tests():
    try:
        schema = SearchQuerySchema()
        data = schema.load(request.args)
        
        user = g.user
        search_term = data.get('q') or data.get('search')
        limit = data.get('limit', 20)
        
        if not search_term or len(search_term) < 2:
            return jsonify({
                'success': False,
                'error': "أدخل كلمة بحث مكونة من حرفين على الأقل"
            }), 400
        
        db = get_db()
        cursor = db.cursor()
        
        search_query = f"%{search_term}%"
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT id, date, title, subtitle, result, created_at 
                FROM medical_tests 
                WHERE user_id = %s AND (
                    title LIKE %s OR 
                    subtitle LIKE %s OR 
                    result LIKE %s OR 
                    notes LIKE %s
                )
                ORDER BY date DESC 
                LIMIT %s
            """, (user['id'], search_query, search_query, search_query, search_query, limit))
        else:
            cursor.execute("""
                SELECT id, date, title, subtitle, result, created_at 
                FROM medical_tests 
                WHERE user_id = ? AND (
                    title LIKE ? OR 
                    subtitle LIKE ? OR 
                    result LIKE ? OR 
                    notes LIKE ?
                )
                ORDER BY date DESC 
                LIMIT ?
            """, (user['id'], search_query, search_query, search_query, search_query, limit))
        
        tests_result = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dicts
        tests = []
        for test in tests_result:
            if hasattr(test, '_asdict'):
                tests.append(test._asdict())
            elif not isinstance(test, dict):
                tests.append(dict(zip([col[0] for col in cursor.description], test)))
            else:
                tests.append(test)
        
        return jsonify({
            'success': True,
            'data': tests,
            'count': len(tests)
        })
        
    except Exception as error:
        print(f'Search medical tests error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء البحث في الفحوصات الطبية"
        }), 500

# Get recent medical tests
@medical_tests_bp.route('/recent', methods=['GET'])
@auth_middleware
@error_handler
def get_recent_medical_tests():
    try:
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT * FROM medical_tests 
                WHERE user_id = %s 
                ORDER BY date DESC, time DESC 
                LIMIT 10
            """, (user['id'],))
        else:
            cursor.execute("""
                SELECT * FROM medical_tests 
                WHERE user_id = ? 
                ORDER BY date DESC, time DESC 
                LIMIT 10
            """, (user['id'],))
        
        tests_result = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dicts
        tests = []
        for test in tests_result:
            if hasattr(test, '_asdict'):
                tests.append(test._asdict())
            elif not isinstance(test, dict):
                tests.append(dict(zip([col[0] for col in cursor.description], test)))
            else:
                tests.append(test)
        
        return jsonify({
            'success': True,
            'data': tests,
            'count': len(tests)
        })
        
    except Exception as error:
        print(f'Get recent medical tests error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب الفحوصات الطبية الحديثة"
        }), 500