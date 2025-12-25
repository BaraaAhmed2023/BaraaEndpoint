from flask import Blueprint, request, jsonify, g, current_app
import uuid
from datetime import datetime
from ..middleware import auth_middleware, error_handler
from ..schemas import DailyStatCreateSchema, PaginationSchema
from ..utils.health_validators import validate_blood_pressure, validate_sugar_level, analyze_trends
from ..models import get_db

daily_stats_bp = Blueprint('daily_stats', __name__)

# Apply middleware to all routes
daily_stats_bp.before_request
def before_request():
    pass

# Get all daily stats with pagination
@daily_stats_bp.route('/', methods=['GET'])
@auth_middleware
@error_handler
def get_daily_stats():
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
                "SELECT COUNT(*) as total FROM daily_stats WHERE user_id = %s",
                (user['id'],)
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) as total FROM daily_stats WHERE user_id = ?",
                (user['id'],)
            )
        
        count_result = cursor.fetchone()
        total = count_result[0] if count_result else 0
        
        # Get stats
        order_clause = f"{sort} {order.upper()}"
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(f"""
                SELECT * FROM daily_stats 
                WHERE user_id = %s 
                ORDER BY {order_clause}
                LIMIT %s OFFSET %s
            """, (user['id'], limit, offset))
        else:
            cursor.execute(f"""
                SELECT * FROM daily_stats 
                WHERE user_id = ? 
                ORDER BY {order_clause}
                LIMIT ? OFFSET ?
            """, (user['id'], limit, offset))
        
        stats_result = cursor.fetchall()
        cursor.close()
        
        # Add health analysis
        stats_with_analysis = []
        for stat in stats_result:
            if hasattr(stat, '_asdict'):
                stat_dict = stat._asdict()
            elif not isinstance(stat, dict):
                stat_dict = dict(zip([col[0] for col in cursor.description], stat))
            else:
                stat_dict = stat
            
            bp_analysis = validate_blood_pressure(
                stat_dict['blood_pressure_systolic'], 
                stat_dict['blood_pressure_diastolic']
            )
            sugar_analysis = validate_sugar_level(stat_dict['sugar_level'])
            
            stat_dict['bp_analysis'] = bp_analysis
            stat_dict['sugar_analysis'] = sugar_analysis
            stat_dict['overall_status'] = 'good' if (
                bp_analysis['status'] == 'good' and sugar_analysis['status'] == 'good'
            ) else 'warning'
            
            stats_with_analysis.append(stat_dict)
        
        return jsonify({
            'success': True,
            'data': stats_with_analysis,
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
        print(f'Get daily stats error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب الإحصائيات اليومية"
        }), 500

# Create daily stat
@daily_stats_bp.route('/', methods=['POST'])
@auth_middleware
@error_handler
def create_daily_stat():
    try:
        schema = DailyStatCreateSchema()
        data = schema.load(request.json)
        
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        stat_id = str(uuid.uuid4())
        date = data.get('date') or datetime.utcnow().date().isoformat()
        now = datetime.utcnow()
        
        # Check if stat already exists for this date
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT id FROM daily_stats WHERE user_id = %s AND date = %s",
                (user['id'], date)
            )
        else:
            cursor.execute(
                "SELECT id FROM daily_stats WHERE user_id = ? AND date = ?",
                (user['id'], date)
            )
        
        existing = cursor.fetchone()
        
        if existing:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "تم تسجيل إحصائيات لهذا اليوم بالفعل"
            }), 409
        
        # Insert new stat
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                INSERT INTO daily_stats (
                    id, user_id, date, sugar_level, blood_pressure_systolic,
                    blood_pressure_diastolic, notes, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                stat_id,
                user['id'],
                date,
                data['sugar_level'],
                data['blood_pressure_systolic'],
                data['blood_pressure_diastolic'],
                data.get('notes'),
                now
            ))
        else:
            cursor.execute("""
                INSERT INTO daily_stats (
                    id, user_id, date, sugar_level, blood_pressure_systolic,
                    blood_pressure_diastolic, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                stat_id,
                user['id'],
                date,
                data['sugar_level'],
                data['blood_pressure_systolic'],
                data['blood_pressure_diastolic'],
                data.get('notes'),
                now
            ))
        
        db.commit()
        
        # Get the created stat
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT * FROM daily_stats WHERE id = %s",
                (stat_id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM daily_stats WHERE id = ?",
                (stat_id,)
            )
        
        stat = cursor.fetchone()
        
        # Add analysis
        bp_analysis = validate_blood_pressure(
            data['blood_pressure_systolic'], 
            data['blood_pressure_diastolic']
        )
        sugar_analysis = validate_sugar_level(data['sugar_level'])
        
        if hasattr(stat, '_asdict'):
            stat_dict = stat._asdict()
        elif not isinstance(stat, dict):
            stat_dict = dict(zip([col[0] for col in cursor.description], stat))
        else:
            stat_dict = stat
        
        stat_dict['bp_analysis'] = bp_analysis
        stat_dict['sugar_analysis'] = sugar_analysis
        stat_dict['overall_status'] = 'good' if (
            bp_analysis['status'] == 'good' and sugar_analysis['status'] == 'good'
        ) else 'warning'
        
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': "تم تسجيل الإحصائيات اليومية بنجاح",
            'data': stat_dict
        }), 201
        
    except Exception as error:
        print(f'Create daily stat error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء تسجيل الإحصائيات اليومية"
        }), 500

# Get stats for specific date
@daily_stats_bp.route('/date/<string:date>', methods=['GET'])
@auth_middleware
@error_handler
def get_stat_by_date(date):
    try:
        user = g.user
        
        # Validate date format
        import re
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
            return jsonify({
                'success': False,
                'error': "صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD"
            }), 400
        
        db = get_db()
        cursor = db.cursor()
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT * FROM daily_stats WHERE user_id = %s AND date = %s",
                (user['id'], date)
            )
        else:
            cursor.execute(
                "SELECT * FROM daily_stats WHERE user_id = ? AND date = ?",
                (user['id'], date)
            )
        
        stat = cursor.fetchone()
        cursor.close()
        
        if not stat:
            return jsonify({
                'success': False,
                'error': "لا توجد إحصائيات مسجلة لهذا التاريخ"
            }), 404
        
        # Convert to dict
        if hasattr(stat, '_asdict'):
            stat_dict = stat._asdict()
        elif not isinstance(stat, dict):
            stat_dict = dict(zip([col[0] for col in cursor.description], stat))
        else:
            stat_dict = stat
        
        # Add analysis
        bp_analysis = validate_blood_pressure(
            stat_dict['blood_pressure_systolic'], 
            stat_dict['blood_pressure_diastolic']
        )
        sugar_analysis = validate_sugar_level(stat_dict['sugar_level'])
        
        stat_dict['bp_analysis'] = bp_analysis
        stat_dict['sugar_analysis'] = sugar_analysis
        stat_dict['overall_status'] = 'good' if (
            bp_analysis['status'] == 'good' and sugar_analysis['status'] == 'good'
        ) else 'warning'
        
        return jsonify({
            'success': True,
            'data': stat_dict
        })
        
    except Exception as error:
        print(f'Get stat by date error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب إحصائيات اليوم"
        }), 500

# Get stats summary (last 30 days)
@daily_stats_bp.route('/summary', methods=['GET'])
@auth_middleware
@error_handler
def get_stats_summary():
    try:
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        # Get last 30 days of stats
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT * FROM daily_stats 
                WHERE user_id = %s 
                ORDER BY date DESC 
                LIMIT 30
            """, (user['id'],))
        else:
            cursor.execute("""
                SELECT * FROM daily_stats 
                WHERE user_id = ? 
                ORDER BY date DESC 
                LIMIT 30
            """, (user['id'],))
        
        stats_result = cursor.fetchall()
        cursor.close()
        
        if not stats_result:
            return jsonify({
                'success': True,
                'data': [],
                'analysis': {
                    'message': "لا توجد بيانات كافية للتحليل"
                }
            })
        
        # Convert to list of dicts
        stats = []
        for stat in stats_result:
            if hasattr(stat, '_asdict'):
                stat_dict = stat._asdict()
            elif not isinstance(stat, dict):
                stat_dict = dict(zip([col[0] for col in cursor.description], stat))
            else:
                stat_dict = stat
            stats.append(stat_dict)
        
        # Calculate averages
        if stats:
            averages = {
                'sugar_level': sum(stat['sugar_level'] for stat in stats) / len(stats),
                'blood_pressure_systolic': sum(stat['blood_pressure_systolic'] for stat in stats) / len(stats),
                'blood_pressure_diastolic': sum(stat['blood_pressure_diastolic'] for stat in stats) / len(stats)
            }
        else:
            averages = {
                'sugar_level': 0,
                'blood_pressure_systolic': 0,
                'blood_pressure_diastolic': 0
            }
        
        # Analyze trends
        trends = analyze_trends(stats)
        
        # Get latest stat for current status
        if stats:
            latest_stat = stats[0]
            current_status = {
                'sugar': validate_sugar_level(latest_stat['sugar_level']),
                'blood_pressure': validate_blood_pressure(
                    latest_stat['blood_pressure_systolic'], 
                    latest_stat['blood_pressure_diastolic']
                )
            }
        else:
            current_status = {
                'sugar': {'category': 'غير متوفر', 'status': 'unknown'},
                'blood_pressure': {'category': 'غير متوفر', 'status': 'unknown'}
            }
        
        return jsonify({
            'success': True,
            'data': {
                'count': len(stats),
                'averages': averages,
                'current_status': current_status,
                'trends': trends,
                'latest_stats': stats[:7]  # Last 7 days
            }
        })
        
    except Exception as error:
        print(f'Get stats summary error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب ملخص الإحصائيات"
        }), 500

# Update daily stat
@daily_stats_bp.route('/<string:id>', methods=['PUT'])
@auth_middleware
@error_handler
def update_daily_stat(id):
    try:
        schema = DailyStatCreateSchema()
        data = schema.load(request.json)
        
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        # Check if stat exists
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT id FROM daily_stats WHERE id = %s AND user_id = %s",
                (id, user['id'])
            )
        else:
            cursor.execute(
                "SELECT id FROM daily_stats WHERE id = ? AND user_id = ?",
                (id, user['id'])
            )
        
        existing = cursor.fetchone()
        
        if not existing:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "الإحصائيات غير موجودة أو ليس لديك صلاحية التعديل عليها"
            }), 404
        
        # Build update query
        updates = []
        values = []
        
        if 'date' in data:
            updates.append("date = %s")
            values.append(data['date'])
        
        if 'sugar_level' in data:
            updates.append("sugar_level = %s")
            values.append(data['sugar_level'])
        
        if 'blood_pressure_systolic' in data:
            updates.append("blood_pressure_systolic = %s")
            values.append(data['blood_pressure_systolic'])
        
        if 'blood_pressure_diastolic' in data:
            updates.append("blood_pressure_diastolic = %s")
            values.append(data['blood_pressure_diastolic'])
        
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
        query = f"UPDATE daily_stats SET {', '.join(updates)} WHERE id = %s AND user_id = %s"
        
        if not current_app.config['DATABASE_URL'].startswith('postgresql://'):
            query = query.replace('%s', '?')
        
        cursor.execute(query, values)
        db.commit()
        
        # Get updated stat
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT * FROM daily_stats WHERE id = %s",
                (id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM daily_stats WHERE id = ?",
                (id,)
            )
        
        updated_stat = cursor.fetchone()
        cursor.close()
        
        if hasattr(updated_stat, '_asdict'):
            stat_dict = updated_stat._asdict()
        elif not isinstance(updated_stat, dict):
            stat_dict = dict(zip([col[0] for col in cursor.description], updated_stat))
        else:
            stat_dict = updated_stat
        
        return jsonify({
            'success': True,
            'message': "تم تحديث الإحصائيات بنجاح",
            'data': stat_dict
        })
        
    except Exception as error:
        print(f'Update daily stat error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء تحديث الإحصائيات"
        }), 500

# Delete daily stat
@daily_stats_bp.route('/<string:id>', methods=['DELETE'])
@auth_middleware
@error_handler
def delete_daily_stat(id):
    try:
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        # Check if stat exists
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT id FROM daily_stats WHERE id = %s AND user_id = %s",
                (id, user['id'])
            )
        else:
            cursor.execute(
                "SELECT id FROM daily_stats WHERE id = ? AND user_id = ?",
                (id, user['id'])
            )
        
        existing = cursor.fetchone()
        
        if not existing:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "الإحصائيات غير موجودة أو ليس لديك صلاحية الحذف"
            }), 404
        
        # Delete stat
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "DELETE FROM daily_stats WHERE id = %s AND user_id = %s",
                (id, user['id'])
            )
        else:
            cursor.execute(
                "DELETE FROM daily_stats WHERE id = ? AND user_id = ?",
                (id, user['id'])
            )
        
        db.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': "تم حذف الإحصائيات بنجاح"
        })
        
    except Exception as error:
        print(f'Delete daily stat error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء حذف الإحصائيات"
        }), 500