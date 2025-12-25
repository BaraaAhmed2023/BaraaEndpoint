from flask import Blueprint, request, jsonify, g, current_app
import uuid
from datetime import datetime
from ..middleware import auth_middleware, error_handler
from ..schemas import RecipeCreateSchema, RecipeUpdateSchema, SearchQuerySchema, PaginationSchema
from ..models import get_db

recipes_bp = Blueprint('recipes', __name__)

# Get all recipes with pagination (public)
@recipes_bp.route('/', methods=['GET'])
@error_handler
def get_recipes():
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
            cursor.execute("SELECT COUNT(*) as total FROM recipes")
        else:
            cursor.execute("SELECT COUNT(*) as total FROM recipes")
        
        count_result = cursor.fetchone()
        total = count_result[0] if count_result else 0
        
        # Get recipes with author info
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT r.*, u.username as author_username 
                FROM recipes r
                LEFT JOIN users u ON r.author_id = u.id
                ORDER BY r.created_at DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
        else:
            cursor.execute("""
                SELECT r.*, u.username as author_username 
                FROM recipes r
                LEFT JOIN users u ON r.author_id = u.id
                ORDER BY r.created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
        
        recipes_result = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dicts
        recipes = []
        for recipe in recipes_result:
            if hasattr(recipe, '_asdict'):
                recipes.append(recipe._asdict())
            elif not isinstance(recipe, dict):
                recipes.append(dict(zip([col[0] for col in cursor.description], recipe)))
            else:
                recipes.append(recipe)
        
        return jsonify({
            'success': True,
            'data': recipes,
            'meta': {
                'total': total,
                'page': page,
                'limit': limit,
                'pages': (total + limit - 1) // limit
            }
        })
        
    except Exception as error:
        print(f'Get recipes error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب الوصفات"
        }), 500

# Get single recipe (public)
@recipes_bp.route('/<string:id>', methods=['GET'])
@error_handler
def get_recipe(id):
    try:
        db = get_db()
        cursor = db.cursor()
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT r.*, u.username as author_username 
                FROM recipes r
                LEFT JOIN users u ON r.author_id = u.id
                WHERE r.id = %s
            """, (id,))
        else:
            cursor.execute("""
                SELECT r.*, u.username as author_username 
                FROM recipes r
                LEFT JOIN users u ON r.author_id = u.id
                WHERE r.id = ?
            """, (id,))
        
        recipe = cursor.fetchone()
        cursor.close()
        
        if not recipe:
            return jsonify({
                'success': False,
                'error': "الوصفة غير موجودة"
            }), 404
        
        # Convert to dict
        if hasattr(recipe, '_asdict'):
            recipe_dict = recipe._asdict()
        elif not isinstance(recipe, dict):
            recipe_dict = dict(zip([col[0] for col in cursor.description], recipe))
        else:
            recipe_dict = recipe
        
        return jsonify({
            'success': True,
            'data': recipe_dict
        })
        
    except Exception as error:
        print(f'Get recipe error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب الوصفة"
        }), 500

# Search recipes (public)
@recipes_bp.route('/search', methods=['GET'])
@error_handler
def search_recipes():
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
                SELECT r.*, u.username as author_username 
                FROM recipes r
                LEFT JOIN users u ON r.author_id = u.id
                WHERE r.title LIKE %s OR r.description LIKE %s OR r.ingredients LIKE %s
                ORDER BY r.created_at DESC
                LIMIT %s
            """, (search_query, search_query, search_query, limit))
        else:
            cursor.execute("""
                SELECT r.*, u.username as author_username 
                FROM recipes r
                LEFT JOIN users u ON r.author_id = u.id
                WHERE r.title LIKE ? OR r.description LIKE ? OR r.ingredients LIKE ?
                ORDER BY r.created_at DESC
                LIMIT ?
            """, (search_query, search_query, search_query, limit))
        
        recipes_result = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dicts
        recipes = []
        for recipe in recipes_result:
            if hasattr(recipe, '_asdict'):
                recipes.append(recipe._asdict())
            elif not isinstance(recipe, dict):
                recipes.append(dict(zip([col[0] for col in cursor.description], recipe)))
            else:
                recipes.append(recipe)
        
        return jsonify({
            'success': True,
            'data': recipes,
            'count': len(recipes)
        })
        
    except Exception as error:
        print(f'Search recipes error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء البحث في الوصفات"
        }), 500

# Create recipe (authenticated)
@recipes_bp.route('/', methods=['POST'])
@auth_middleware
@error_handler
def create_recipe():
    try:
        schema = RecipeCreateSchema()
        data = schema.load(request.json)
        
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        recipe_id = f"rx-{uuid.uuid4()}"
        now = datetime.utcnow()
        
        # Insert recipe
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                INSERT INTO recipes (
                    id, author_id, title, description, ingredients, instructions, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                recipe_id,
                user['id'],
                data['title'],
                data.get('description', ''),
                data.get('ingredients', ''),
                data.get('instructions', ''),
                now,
                now
            ))
        else:
            cursor.execute("""
                INSERT INTO recipes (
                    id, author_id, title, description, ingredients, instructions, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                recipe_id,
                user['id'],
                data['title'],
                data.get('description', ''),
                data.get('ingredients', ''),
                data.get('instructions', ''),
                now,
                now
            ))
        
        db.commit()
        
        # Get created recipe with author info
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT r.*, u.username as author_username 
                FROM recipes r
                LEFT JOIN users u ON r.author_id = u.id
                WHERE r.id = %s
            """, (recipe_id,))
        else:
            cursor.execute("""
                SELECT r.*, u.username as author_username 
                FROM recipes r
                LEFT JOIN users u ON r.author_id = u.id
                WHERE r.id = ?
            """, (recipe_id,))
        
        recipe = cursor.fetchone()
        cursor.close()
        
        # Convert to dict
        if hasattr(recipe, '_asdict'):
            recipe_dict = recipe._asdict()
        elif not isinstance(recipe, dict):
            recipe_dict = dict(zip([col[0] for col in cursor.description], recipe))
        else:
            recipe_dict = recipe
        
        return jsonify({
            'success': True,
            'message': "تم إنشاء الوصفة بنجاح",
            'data': recipe_dict
        }), 201
        
    except Exception as error:
        print(f'Create recipe error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء إنشاء الوصفة"
        }), 500

# Update recipe (authenticated - author only)
@recipes_bp.route('/<string:id>', methods=['PUT'])
@auth_middleware
@error_handler
def update_recipe(id):
    try:
        schema = RecipeUpdateSchema()
        data = schema.load(request.json)
        
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        # Check if recipe exists and belongs to user
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT id FROM recipes WHERE id = %s AND author_id = %s",
                (id, user['id'])
            )
        else:
            cursor.execute(
                "SELECT id FROM recipes WHERE id = ? AND author_id = ?",
                (id, user['id'])
            )
        
        existing = cursor.fetchone()
        
        if not existing:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "الوصفة غير موجودة أو ليس لديك صلاحية التعديل عليها"
            }), 404
        
        # Build update query
        updates = []
        values = []
        
        if 'title' in data:
            updates.append("title = %s")
            values.append(data['title'])
        
        if 'description' in data:
            updates.append("description = %s")
            values.append(data['description'])
        
        if 'ingredients' in data:
            updates.append("ingredients = %s")
            values.append(data['ingredients'])
        
        if 'instructions' in data:
            updates.append("instructions = %s")
            values.append(data['instructions'])
        
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
        query = f"UPDATE recipes SET {', '.join(updates)} WHERE id = %s AND author_id = %s"
        
        if not current_app.config['DATABASE_URL'].startswith('postgresql://'):
            query = query.replace('%s', '?')
        
        cursor.execute(query, values)
        db.commit()
        
        # Get updated recipe
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT * FROM recipes WHERE id = %s",
                (id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM recipes WHERE id = ?",
                (id,)
            )
        
        updated_recipe = cursor.fetchone()
        cursor.close()
        
        # Convert to dict
        if hasattr(updated_recipe, '_asdict'):
            recipe_dict = updated_recipe._asdict()
        elif not isinstance(updated_recipe, dict):
            recipe_dict = dict(zip([col[0] for col in cursor.description], updated_recipe))
        else:
            recipe_dict = updated_recipe
        
        return jsonify({
            'success': True,
            'message': "تم تحديث الوصفة بنجاح",
            'data': recipe_dict
        })
        
    except Exception as error:
        print(f'Update recipe error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء تحديث الوصفة"
        }), 500

# Delete recipe (authenticated - author only)
@recipes_bp.route('/<string:id>', methods=['DELETE'])
@auth_middleware
@error_handler
def delete_recipe(id):
    try:
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        # Check if recipe exists and belongs to user
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT id FROM recipes WHERE id = %s AND author_id = %s",
                (id, user['id'])
            )
        else:
            cursor.execute(
                "SELECT id FROM recipes WHERE id = ? AND author_id = ?",
                (id, user['id'])
            )
        
        existing = cursor.fetchone()
        
        if not existing:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "الوصفة غير موجودة أو ليس لديك صلاحية الحذف"
            }), 404
        
        # Delete recipe
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "DELETE FROM recipes WHERE id = %s AND author_id = %s",
                (id, user['id'])
            )
        else:
            cursor.execute(
                "DELETE FROM recipes WHERE id = ? AND author_id = ?",
                (id, user['id'])
            )
        
        db.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': "تم حذف الوصفة بنجاح"
        })
        
    except Exception as error:
        print(f'Delete recipe error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء حذف الوصفة"
        }), 500

# Get user's recipes
@recipes_bp.route('/user/my-recipes', methods=['GET'])
@auth_middleware
@error_handler
def get_user_recipes():
    try:
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT * FROM recipes WHERE author_id = %s ORDER BY created_at DESC
            """, (user['id'],))
        else:
            cursor.execute("""
                SELECT * FROM recipes WHERE author_id = ? ORDER BY created_at DESC
            """, (user['id'],))
        
        recipes_result = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dicts
        recipes = []
        for recipe in recipes_result:
            if hasattr(recipe, '_asdict'):
                recipes.append(recipe._asdict())
            elif not isinstance(recipe, dict):
                recipes.append(dict(zip([col[0] for col in cursor.description], recipe)))
            else:
                recipes.append(recipe)
        
        return jsonify({
            'success': True,
            'data': recipes,
            'count': len(recipes)
        })
        
    except Exception as error:
        print(f'Get user recipes error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب وصفاتك"
        }), 500

# Get popular recipes (most recent)
@recipes_bp.route('/popular', methods=['GET'])
@error_handler
def get_popular_recipes():
    try:
        db = get_db()
        cursor = db.cursor()
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT r.*, u.username as author_username 
                FROM recipes r
                LEFT JOIN users u ON r.author_id = u.id
                ORDER BY r.created_at DESC
                LIMIT 10
            """)
        else:
            cursor.execute("""
                SELECT r.*, u.username as author_username 
                FROM recipes r
                LEFT JOIN users u ON r.author_id = u.id
                ORDER BY r.created_at DESC
                LIMIT 10
            """)
        
        recipes_result = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dicts
        recipes = []
        for recipe in recipes_result:
            if hasattr(recipe, '_asdict'):
                recipes.append(recipe._asdict())
            elif not isinstance(recipe, dict):
                recipes.append(dict(zip([col[0] for col in cursor.description], recipe)))
            else:
                recipes.append(recipe)
        
        return jsonify({
            'success': True,
            'data': recipes
        })
        
    except Exception as error:
        print(f'Get popular recipes error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب الوصفات الشائعة"
        }), 500