from flask import Blueprint, request, jsonify, g, current_app
import uuid
from datetime import datetime
from ..middleware import auth_middleware, error_handler
from ..schemas import (
    HerbCreateSchema, HerbUpdateSchema, HerbStoryCreateSchema, 
    HerbStoryUpdateSchema, SearchQuerySchema, PaginationSchema
)
from ..models import get_db

herbs_bp = Blueprint('herbs', __name__)

# Get all herbs (public)
@herbs_bp.route('/', methods=['GET'])
@error_handler
def get_herbs():
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
            cursor.execute("SELECT COUNT(*) as total FROM herbs")
        else:
            cursor.execute("SELECT COUNT(*) as total FROM herbs")
        
        count_result = cursor.fetchone()
        total = count_result[0] if count_result else 0
        
        # Get herbs
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT * FROM herbs 
                ORDER BY name ASC
                LIMIT %s OFFSET %s
            """, (limit, offset))
        else:
            cursor.execute("""
                SELECT * FROM herbs 
                ORDER BY name ASC
                LIMIT ? OFFSET ?
            """, (limit, offset))
        
        herbs_result = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dicts
        herbs = []
        for herb in herbs_result:
            if hasattr(herb, '_asdict'):
                herbs.append(herb._asdict())
            elif not isinstance(herb, dict):
                herbs.append(dict(zip([col[0] for col in cursor.description], herb)))
            else:
                herbs.append(herb)
        
        return jsonify({
            'success': True,
            'data': herbs,
            'meta': {
                'total': total,
                'page': page,
                'limit': limit,
                'pages': (total + limit - 1) // limit
            }
        })
        
    except Exception as error:
        print(f'Get herbs error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب الأعشاب"
        }), 500

# Get single herb (public)
@herbs_bp.route('/<string:id>', methods=['GET'])
@error_handler
def get_herb(id):
    try:
        db = get_db()
        cursor = db.cursor()
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT * FROM herbs WHERE id = %s",
                (id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM herbs WHERE id = ?",
                (id,)
            )
        
        herb = cursor.fetchone()
        cursor.close()
        
        if not herb:
            return jsonify({
                'success': False,
                'error': "العشبة غير موجودة"
            }), 404
        
        # Convert to dict
        if hasattr(herb, '_asdict'):
            herb_dict = herb._asdict()
        elif not isinstance(herb, dict):
            herb_dict = dict(zip([col[0] for col in cursor.description], herb))
        else:
            herb_dict = herb
        
        return jsonify({
            'success': True,
            'data': herb_dict
        })
        
    except Exception as error:
        print(f'Get herb error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب العشبة"
        }), 500

# Search herbs (public)
@herbs_bp.route('/search', methods=['GET'])
@error_handler
def search_herbs():
    try:
        schema = SearchQuerySchema()
        data = schema.load(request.args)
        
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
                SELECT * FROM herbs 
                WHERE name LIKE %s OR description LIKE %s OR uses LIKE %s
                ORDER BY name ASC
                LIMIT %s
            """, (search_query, search_query, search_query, limit))
        else:
            cursor.execute("""
                SELECT * FROM herbs 
                WHERE name LIKE ? OR description LIKE ? OR uses LIKE ?
                ORDER BY name ASC
                LIMIT ?
            """, (search_query, search_query, search_query, limit))
        
        herbs_result = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dicts
        herbs = []
        for herb in herbs_result:
            if hasattr(herb, '_asdict'):
                herbs.append(herb._asdict())
            elif not isinstance(herb, dict):
                herbs.append(dict(zip([col[0] for col in cursor.description], herb)))
            else:
                herbs.append(herb)
        
        return jsonify({
            'success': True,
            'data': herbs,
            'count': len(herbs)
        })
        
    except Exception as error:
        print(f'Search herbs error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء البحث في الأعشاب"
        }), 500

# Get herb stories (public)
@herbs_bp.route('/<string:id>/stories', methods=['GET'])
@error_handler
def get_herb_stories(id):
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Verify herb exists
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT id FROM herbs WHERE id = %s",
                (id,)
            )
        else:
            cursor.execute(
                "SELECT id FROM herbs WHERE id = ?",
                (id,)
            )
        
        herb = cursor.fetchone()
        
        if not herb:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "العشبة غير موجودة"
            }), 404
        
        # Get stories
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT hs.*, h.name as herb_name 
                FROM herb_stories hs
                JOIN herbs h ON hs.herb_id = h.id
                WHERE hs.herb_id = %s
                ORDER BY hs.created_at DESC
            """, (id,))
        else:
            cursor.execute("""
                SELECT hs.*, h.name as herb_name 
                FROM herb_stories hs
                JOIN herbs h ON hs.herb_id = h.id
                WHERE hs.herb_id = ?
                ORDER BY hs.created_at DESC
            """, (id,))
        
        stories_result = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dicts
        stories = []
        for story in stories_result:
            if hasattr(story, '_asdict'):
                stories.append(story._asdict())
            elif not isinstance(story, dict):
                stories.append(dict(zip([col[0] for col in cursor.description], story)))
            else:
                stories.append(story)
        
        return jsonify({
            'success': True,
            'data': stories,
            'count': len(stories)
        })
        
    except Exception as error:
        print(f'Get herb stories error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب قصص العشبة"
        }), 500

# Create herb (admin only - currently allowing any authenticated user)
@herbs_bp.route('/', methods=['POST'])
@auth_middleware
@error_handler
def create_herb():
    try:
        schema = HerbCreateSchema()
        data = schema.load(request.json)
        
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        herb_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Insert herb
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                INSERT INTO herbs (
                    id, name, description, uses, benefits, harms, image_url, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                herb_id,
                data['name'],
                data['description'],
                data['uses'],
                data.get('benefits'),
                data.get('harms'),
                data.get('image_url'),
                now
            ))
        else:
            cursor.execute("""
                INSERT INTO herbs (
                    id, name, description, uses, benefits, harms, image_url, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                herb_id,
                data['name'],
                data['description'],
                data['uses'],
                data.get('benefits'),
                data.get('harms'),
                data.get('image_url'),
                now
            ))
        
        db.commit()
        
        # Get created herb
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT * FROM herbs WHERE id = %s",
                (herb_id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM herbs WHERE id = ?",
                (herb_id,)
            )
        
        herb = cursor.fetchone()
        cursor.close()
        
        # Convert to dict
        if hasattr(herb, '_asdict'):
            herb_dict = herb._asdict()
        elif not isinstance(herb, dict):
            herb_dict = dict(zip([col[0] for col in cursor.description], herb))
        else:
            herb_dict = herb
        
        return jsonify({
            'success': True,
            'message': "تم إنشاء العشبة بنجاح",
            'data': herb_dict
        }), 201
        
    except Exception as error:
        print(f'Create herb error: {error}')
        # Check if unique constraint failed
        if 'unique' in str(error).lower() or 'UNIQUE' in str(error):
            return jsonify({
                'success': False,
                'error': "اسم العشبة موجود مسبقاً"
            }), 409
        
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء إنشاء العشبة"
        }), 500

# Update herb (admin only)
@herbs_bp.route('/<string:id>', methods=['PUT'])
@auth_middleware
@error_handler
def update_herb(id):
    try:
        schema = HerbUpdateSchema()
        data = schema.load(request.json)
        
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        # Check if herb exists
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT id FROM herbs WHERE id = %s",
                (id,)
            )
        else:
            cursor.execute(
                "SELECT id FROM herbs WHERE id = ?",
                (id,)
            )
        
        existing = cursor.fetchone()
        
        if not existing:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "العشبة غير موجودة"
            }), 404
        
        # Build update query
        updates = []
        values = []
        
        if 'name' in data:
            updates.append("name = %s")
            values.append(data['name'])
        
        if 'description' in data:
            updates.append("description = %s")
            values.append(data['description'])
        
        if 'uses' in data:
            updates.append("uses = %s")
            values.append(data['uses'])
        
        if 'benefits' in data:
            updates.append("benefits = %s")
            values.append(data['benefits'])
        
        if 'harms' in data:
            updates.append("harms = %s")
            values.append(data['harms'])
        
        if 'image_url' in data:
            updates.append("image_url = %s")
            values.append(data['image_url'])
        
        if not updates:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "لا توجد بيانات للتحديث"
            }), 400
        
        values.append(id)
        
        # Build SQL query
        query = f"UPDATE herbs SET {', '.join(updates)} WHERE id = %s"
        
        if not current_app.config['DATABASE_URL'].startswith('postgresql://'):
            query = query.replace('%s', '?')
        
        cursor.execute(query, values)
        db.commit()
        
        # Get updated herb
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT * FROM herbs WHERE id = %s",
                (id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM herbs WHERE id = ?",
                (id,)
            )
        
        updated_herb = cursor.fetchone()
        cursor.close()
        
        # Convert to dict
        if hasattr(updated_herb, '_asdict'):
            herb_dict = updated_herb._asdict()
        elif not isinstance(updated_herb, dict):
            herb_dict = dict(zip([col[0] for col in cursor.description], updated_herb))
        else:
            herb_dict = updated_herb
        
        return jsonify({
            'success': True,
            'message': "تم تحديث العشبة بنجاح",
            'data': herb_dict
        })
        
    except Exception as error:
        print(f'Update herb error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء تحديث العشبة"
        }), 500

# Create herb story (admin only)
@herbs_bp.route('/<string:id>/stories', methods=['POST'])
@auth_middleware
@error_handler
def create_herb_story(id):
    try:
        schema = HerbStoryCreateSchema()
        data = schema.load(request.json)
        
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        # Verify herb exists
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT id FROM herbs WHERE id = %s",
                (id,)
            )
        else:
            cursor.execute(
                "SELECT id FROM herbs WHERE id = ?",
                (id,)
            )
        
        herb = cursor.fetchone()
        
        if not herb:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "العشبة غير موجودة"
            }), 404
        
        story_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Insert story
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                INSERT INTO herb_stories (
                    id, title, herb_id, short_description, story, image_url, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                story_id,
                data['title'],
                id,
                data['short_description'],
                data['story'],
                data.get('image_url'),
                now
            ))
        else:
            cursor.execute("""
                INSERT INTO herb_stories (
                    id, title, herb_id, short_description, story, image_url, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                story_id,
                data['title'],
                id,
                data['short_description'],
                data['story'],
                data.get('image_url'),
                now
            ))
        
        db.commit()
        
        # Get created story with herb name
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT hs.*, h.name as herb_name 
                FROM herb_stories hs
                JOIN herbs h ON hs.herb_id = h.id
                WHERE hs.id = %s
            """, (story_id,))
        else:
            cursor.execute("""
                SELECT hs.*, h.name as herb_name 
                FROM herb_stories hs
                JOIN herbs h ON hs.herb_id = h.id
                WHERE hs.id = ?
            """, (story_id,))
        
        story = cursor.fetchone()
        cursor.close()
        
        # Convert to dict
        if hasattr(story, '_asdict'):
            story_dict = story._asdict()
        elif not isinstance(story, dict):
            story_dict = dict(zip([col[0] for col in cursor.description], story))
        else:
            story_dict = story
        
        return jsonify({
            'success': True,
            'message': "تم إنشاء القصة بنجاح",
            'data': story_dict
        }), 201
        
    except Exception as error:
        print(f'Create herb story error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء إنشاء قصة العشبة"
        }), 500

# Get all stories (public)
@herbs_bp.route('/stories/all', methods=['GET'])
@error_handler
def get_all_stories():
    try:
        db = get_db()
        cursor = db.cursor()
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT hs.*, h.name as herb_name 
                FROM herb_stories hs
                JOIN herbs h ON hs.herb_id = h.id
                ORDER BY hs.created_at DESC
            """)
        else:
            cursor.execute("""
                SELECT hs.*, h.name as herb_name 
                FROM herb_stories hs
                JOIN herbs h ON hs.herb_id = h.id
                ORDER BY hs.created_at DESC
            """)
        
        stories_result = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dicts
        stories = []
        for story in stories_result:
            if hasattr(story, '_asdict'):
                stories.append(story._asdict())
            elif not isinstance(story, dict):
                stories.append(dict(zip([col[0] for col in cursor.description], story)))
            else:
                stories.append(story)
        
        return jsonify({
            'success': True,
            'data': stories,
            'count': len(stories)
        })
        
    except Exception as error:
        print(f'Get all stories error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب جميع القصص"
        }), 500