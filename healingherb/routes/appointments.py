from flask import Blueprint, request, jsonify, g, current_app
import uuid
from datetime import datetime
from ..middleware import auth_middleware, error_handler
from ..schemas import AppointmentCreateSchema, AppointmentUpdateSchema, PaginationSchema
from ..models import get_db

appointments_bp = Blueprint('appointments', __name__)

# Get all appointments with pagination
@appointments_bp.route('/', methods=['GET'])
@auth_middleware
@error_handler
def get_appointments():
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
                "SELECT COUNT(*) as total FROM appointments WHERE user_id = %s",
                (user['id'],)
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) as total FROM appointments WHERE user_id = ?",
                (user['id'],)
            )
        
        count_result = cursor.fetchone()
        total = count_result[0] if count_result else 0
        
        # Get appointments
        order_clause = f"{sort} {order.upper()}"
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(f"""
                SELECT * FROM appointments 
                WHERE user_id = %s 
                ORDER BY {order_clause}
                LIMIT %s OFFSET %s
            """, (user['id'], limit, offset))
        else:
            cursor.execute(f"""
                SELECT * FROM appointments 
                WHERE user_id = ? 
                ORDER BY {order_clause}
                LIMIT ? OFFSET ?
            """, (user['id'], limit, offset))
        
        appointments_result = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dicts
        appointments = []
        for appointment in appointments_result:
            if hasattr(appointment, '_asdict'):
                appointments.append(appointment._asdict())
            elif not isinstance(appointment, dict):
                appointments.append(dict(zip([col[0] for col in cursor.description], appointment)))
            else:
                appointments.append(appointment)
        
        return jsonify({
            'success': True,
            'data': appointments,
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
        print(f'Get appointments error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب المواعيد"
        }), 500

# Get single appointment
@appointments_bp.route('/<string:id>', methods=['GET'])
@auth_middleware
@error_handler
def get_appointment(id):
    try:
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT * FROM appointments WHERE id = %s AND user_id = %s",
                (id, user['id'])
            )
        else:
            cursor.execute(
                "SELECT * FROM appointments WHERE id = ? AND user_id = ?",
                (id, user['id'])
            )
        
        appointment = cursor.fetchone()
        cursor.close()
        
        if not appointment:
            return jsonify({
                'success': False,
                'error': "الموعد غير موجود أو ليس لديك صلاحية الوصول إليه"
            }), 404
        
        # Convert to dict
        if hasattr(appointment, '_asdict'):
            appointment_dict = appointment._asdict()
        elif not isinstance(appointment, dict):
            appointment_dict = dict(zip([col[0] for col in cursor.description], appointment))
        else:
            appointment_dict = appointment
        
        return jsonify({
            'success': True,
            'data': appointment_dict
        })
        
    except Exception as error:
        print(f'Get appointment error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب الموعد"
        }), 500

# Create appointment
@appointments_bp.route('/', methods=['POST'])
@auth_middleware
@error_handler
def create_appointment():
    try:
        schema = AppointmentCreateSchema()
        data = schema.load(request.json)
        
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        appointment_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Check if appointment date is in the future
        appointment_date = datetime.strptime(data['date'], '%Y-%m-%d')
        if appointment_date.date() < datetime.utcnow().date():
            return jsonify({
                'success': False,
                'error': "لا يمكن إنشاء موعد بتاريخ سابق"
            }), 400
        
        # Insert appointment
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                INSERT INTO appointments (
                    id, user_id, appointments_to, date, time, location, 
                    appointment_type, notes_or_details, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                appointment_id,
                user['id'],
                data.get('name', ''),
                data['date'],
                data['time'],
                data['location'],
                data.get('appointment_type', 'regular'),
                data.get('notes_or_details'),
                now
            ))
        else:
            cursor.execute("""
                INSERT INTO appointments (
                    id, user_id, appointments_to, date, time, location, 
                    appointment_type, notes_or_details, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                appointment_id,
                user['id'],
                data.get('name', ''),
                data['date'],
                data['time'],
                data['location'],
                data.get('appointment_type', 'regular'),
                data.get('notes_or_details'),
                now
            ))
        
        db.commit()
        
        # Get created appointment
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT * FROM appointments WHERE id = %s",
                (appointment_id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM appointments WHERE id = ?",
                (appointment_id,)
            )
        
        appointment = cursor.fetchone()
        cursor.close()
        
        # Convert to dict
        if hasattr(appointment, '_asdict'):
            appointment_dict = appointment._asdict()
        elif not isinstance(appointment, dict):
            appointment_dict = dict(zip([col[0] for col in cursor.description], appointment))
        else:
            appointment_dict = appointment
        
        return jsonify({
            'success': True,
            'message': "تم إنشاء الموعد بنجاح",
            'data': appointment_dict
        }), 201
        
    except Exception as error:
        print(f'Create appointment error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء إنشاء الموعد"
        }), 500

# Update appointment
@appointments_bp.route('/<string:id>', methods=['PUT'])
@auth_middleware
@error_handler
def update_appointment(id):
    try:
        schema = AppointmentUpdateSchema()
        data = schema.load(request.json)
        
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        # Check if appointment exists
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT id FROM appointments WHERE id = %s AND user_id = %s",
                (id, user['id'])
            )
        else:
            cursor.execute(
                "SELECT id FROM appointments WHERE id = ? AND user_id = ?",
                (id, user['id'])
            )
        
        existing = cursor.fetchone()
        
        if not existing:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "الموعد غير موجود أو ليس لديك صلاحية التعديل عليه"
            }), 404
        
        # Build update query
        updates = []
        values = []
        
        if 'name' in data:
            updates.append("appointments_to = %s")
            values.append(data['name'])
        
        if 'date' in data:
            updates.append("date = %s")
            values.append(data['date'])
        
        if 'time' in data:
            updates.append("time = %s")
            values.append(data['time'])
        
        if 'location' in data:
            updates.append("location = %s")
            values.append(data['location'])
        
        if 'appointment_type' in data:
            updates.append("appointment_type = %s")
            values.append(data['appointment_type'])
        
        if 'notes_or_details' in data:
            updates.append("notes_or_details = %s")
            values.append(data['notes_or_details'])
        
        if not updates:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "لا توجد بيانات للتحديث"
            }), 400
        
        values.extend([id, user['id']])
        
        # Build SQL query
        query = f"UPDATE appointments SET {', '.join(updates)} WHERE id = %s AND user_id = %s"
        
        if not current_app.config['DATABASE_URL'].startswith('postgresql://'):
            query = query.replace('%s', '?')
        
        cursor.execute(query, values)
        db.commit()
        
        # Get updated appointment
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT * FROM appointments WHERE id = %s",
                (id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM appointments WHERE id = ?",
                (id,)
            )
        
        updated_appointment = cursor.fetchone()
        cursor.close()
        
        # Convert to dict
        if hasattr(updated_appointment, '_asdict'):
            appointment_dict = updated_appointment._asdict()
        elif not isinstance(updated_appointment, dict):
            appointment_dict = dict(zip([col[0] for col in cursor.description], updated_appointment))
        else:
            appointment_dict = updated_appointment
        
        return jsonify({
            'success': True,
            'message': "تم تحديث الموعد بنجاح",
            'data': appointment_dict
        })
        
    except Exception as error:
        print(f'Update appointment error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء تحديث الموعد"
        }), 500

# Delete appointment
@appointments_bp.route('/<string:id>', methods=['DELETE'])
@auth_middleware
@error_handler
def delete_appointment(id):
    try:
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        # Check if appointment exists
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "SELECT id FROM appointments WHERE id = %s AND user_id = %s",
                (id, user['id'])
            )
        else:
            cursor.execute(
                "SELECT id FROM appointments WHERE id = ? AND user_id = ?",
                (id, user['id'])
            )
        
        existing = cursor.fetchone()
        
        if not existing:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "الموعد غير موجود أو ليس لديك صلاحية الحذف"
            }), 404
        
        # Delete appointment
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute(
                "DELETE FROM appointments WHERE id = %s AND user_id = %s",
                (id, user['id'])
            )
        else:
            cursor.execute(
                "DELETE FROM appointments WHERE id = ? AND user_id = ?",
                (id, user['id'])
            )
        
        db.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': "تم حذف الموعد بنجاح"
        })
        
    except Exception as error:
        print(f'Delete appointment error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء حذف الموعد"
        }), 500

# Get upcoming appointments
@appointments_bp.route('/upcoming', methods=['GET'])
@auth_middleware
@error_handler
def get_upcoming_appointments():
    try:
        user = g.user
        db = get_db()
        cursor = db.cursor()
        
        today = datetime.utcnow().date().isoformat()
        
        if current_app.config['DATABASE_URL'].startswith('postgresql://'):
            cursor.execute("""
                SELECT * FROM appointments 
                WHERE user_id = %s AND date >= %s 
                ORDER BY date ASC, time ASC 
                LIMIT 10
            """, (user['id'], today))
        else:
            cursor.execute("""
                SELECT * FROM appointments 
                WHERE user_id = ? AND date >= ? 
                ORDER BY date ASC, time ASC 
                LIMIT 10
            """, (user['id'], today))
        
        appointments_result = cursor.fetchall()
        cursor.close()
        
        # Convert to list of dicts
        appointments = []
        for appointment in appointments_result:
            if hasattr(appointment, '_asdict'):
                appointments.append(appointment._asdict())
            elif not isinstance(appointment, dict):
                appointments.append(dict(zip([col[0] for col in cursor.description], appointment)))
            else:
                appointments.append(appointment)
        
        return jsonify({
            'success': True,
            'data': appointments,
            'count': len(appointments)
        })
        
    except Exception as error:
        print(f'Get upcoming appointments error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء جلب المواعيد القادمة"
        }), 500