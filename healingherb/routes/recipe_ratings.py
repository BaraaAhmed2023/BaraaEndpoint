from flask import Blueprint, request, jsonify, g, current_app
import uuid
from datetime import datetime
from ..middleware import auth_middleware, error_handler
from ..schemas import RecipeRatingSchema
from ..models import get_db

recipe_ratings_bp = Blueprint('recipe_ratings', __name__)

# Rate a recipe (insert/update)
@recipe_ratings_bp.route('/<string:id>/rate', methods=['POST'])
@auth_middleware
@error_handler
def rate_recipe(id):
    try:
        user = g.user
        recipe_id = id
        schema = RecipeRatingSchema()
        data = schema.load(request.json)
        
        db = get_db()
        cursor = db.cursor()
        
        rate_id = f"rate-{uuid.uuid4()}"
        now = datetime.utcnow()
        
        # Check if rating exists for PostgreSQL
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            # First check if rating exists
            cursor.execute("""
                SELECT id FROM recipe_ratings WHERE recipe_id = %s AND user_id = %s
            """, (recipe_id, user['id']))
            
            existing_rating = cursor.fetchone()
            
            if existing_rating:
                # Update existing rating
                cursor.execute("""
                    UPDATE recipe_ratings SET 
                        rating = %s,
                        updated_at = %s
                    WHERE recipe_id = %s AND user_id = %s
                """, (data['rating'], now, recipe_id, user['id']))
            else:
                # Insert new rating
                cursor.execute("""
                    INSERT INTO recipe_ratings (id, recipe_id, user_id, rating, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (rate_id, recipe_id, user['id'], data['rating'], now, now))
        else:
            # For SQLite, use INSERT OR REPLACE
            cursor.execute("""
                INSERT OR REPLACE INTO recipe_ratings (id, recipe_id, user_id, rating, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (rate_id, recipe_id, user['id'], data['rating'], now, now))
        
        db.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': "تم تحديث التقييم بنجاح"
        })
        
    except Exception as error:
        print(f'Rate recipe error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء التقييم"
        }), 500

# Get famous recipes (top rated)
@recipe_ratings_bp.route('/famous', methods=['GET'])
@error_handler
def get_famous_recipes():
    try:
        db = get_db()
        cursor = db.cursor()
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT r.*, u.username AS author_username,
                       AVG(rr.rating) AS avg_rating,
                       COUNT(rr.rating) AS rating_count
                FROM recipes r
                LEFT JOIN users u ON r.author_id = u.id
                LEFT JOIN recipe_ratings rr ON r.id = rr.recipe_id
                GROUP BY r.id, u.username
                ORDER BY avg_rating DESC NULLS LAST, rating_count DESC
                LIMIT 10
            """)
        else:
            cursor.execute("""
                SELECT r.*, u.username AS author_username,
                       AVG(rr.rating) AS avg_rating,
                       COUNT(rr.rating) AS rating_count
                FROM recipes r
                LEFT JOIN users u ON r.author_id = u.id
                LEFT JOIN recipe_ratings rr ON r.id = rr.recipe_id
                GROUP BY r.id
                ORDER BY avg_rating DESC, rating_count DESC
                LIMIT 10
            """)
        
        top_recipes_result = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dicts
        top_recipes = []
        for recipe in top_recipes_result:
            if hasattr(recipe, '_asdict'):
                recipe_dict = recipe._asdict()
            elif not isinstance(recipe, dict):
                recipe_dict = dict(zip([col[0] for col in cursor.description], recipe))
            else:
                recipe_dict = recipe
            
            # Convert Decimal to float for JSON serialization
            if 'avg_rating' in recipe_dict and recipe_dict['avg_rating'] is not None:
                recipe_dict['avg_rating'] = float(recipe_dict['avg_rating'])
            
            top_recipes.append(recipe_dict)
        
        return jsonify({
            'success': True,
            'data': top_recipes
        })
        
    except Exception as error:
        print(f'Get famous recipes error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب الوصفات المشهورة"
        }), 500

# Get ratings for a recipe
@recipe_ratings_bp.route('/<string:id>', methods=['GET'])
@error_handler
def get_recipe_ratings(id):
    try:
        recipe_id = id
        db = get_db()
        cursor = db.cursor()
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT rr.*, u.username as user_username
                FROM recipe_ratings rr
                LEFT JOIN users u ON rr.user_id = u.id
                WHERE rr.recipe_id = %s
            """, (recipe_id,))
        else:
            cursor.execute("""
                SELECT rr.*, u.username as user_username
                FROM recipe_ratings rr
                LEFT JOIN users u ON rr.user_id = u.id
                WHERE rr.recipe_id = ?
            """, (recipe_id,))
        
        ratings_result = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dicts
        ratings = []
        total_rating = 0
        
        for rating in ratings_result:
            if hasattr(rating, '_asdict'):
                rating_dict = rating._asdict()
            elif not isinstance(rating, dict):
                rating_dict = dict(zip([col[0] for col in cursor.description], rating))
            else:
                rating_dict = rating
            
            ratings.append(rating_dict)
            total_rating += rating_dict['rating']
        
        # Calculate average rating
        avg_rating = total_rating / len(ratings) if ratings else 0
        
        return jsonify({
            'success': True,
            'data': ratings,
            'avg_rating': avg_rating
        })
        
    except Exception as error:
        print(f'Get recipe ratings error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب التقييمات"
        }), 500