from flask import Blueprint, request, jsonify, g, current_app
import uuid
from datetime import datetime
from ..middleware import auth_middleware, error_handler
from ..utils.health_validators import validate_blood_pressure, validate_sugar_level, analyze_trends
from ..models import get_db

reports_bp = Blueprint('reports', __name__)

def format_arabic_date(date):
    """Format date in Arabic"""
    try:
        # Arabic month names
        arabic_months = {
            1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل',
            5: 'مايو', 6: 'يونيو', 7: 'يوليو', 8: 'أغسطس',
            9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'
        }
        
        # Arabic day names
        arabic_days = {
            0: 'الأحد', 1: 'الإثنين', 2: 'الثلاثاء', 3: 'الأربعاء',
            4: 'الخميس', 5: 'الجمعة', 6: 'السبت'
        }
        
        day_name = arabic_days[date.weekday()]
        day = date.day
        month = arabic_months[date.month]
        year = date.year
        
        return f"{day_name}، {day} {month} {year}"
    except:
        # Fallback format
        return date.strftime('%Y-%m-%d')

# Generate health report JSON
@reports_bp.route('/health', methods=['GET'])
@auth_middleware
@error_handler
def generate_health_report():
    try:
        user = g.user
        
        # Parse query parameters
        title = request.args.get('title', 'التقرير الصحي الشامل')
        include_recipes = request.args.get('include_recipes', 'false').lower() == 'true'
        include_stats = request.args.get('include_stats', 'true').lower() != 'false'
        include_tests = request.args.get('include_tests', 'true').lower() != 'false'
        include_appointments = request.args.get('include_appointments', 'true').lower() != 'false'
        theme = request.args.get('theme', 'medical')
        
        db = get_db()
        cursor = db.cursor()
        
        # Get user profile
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
        
        profile_result = cursor.fetchone()
        
        if not profile_result:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "المستخدم غير موجود"
            }), 404
        
        # Convert profile to dict
        if hasattr(profile_result, '_asdict'):
            profile = profile_result._asdict()
        elif not isinstance(profile_result, dict):
            profile = dict(zip([col[0] for col in cursor.description], profile_result))
        else:
            profile = profile_result
        
        # Initialize data objects
        daily_stats = []
        medical_tests = []
        appointments = []
        recipes = []
        health_summary = {}
        
        # Get daily stats if requested
        if include_stats:
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
            
            # Convert to list of dicts
            for stat in stats_result:
                if hasattr(stat, '_asdict'):
                    stat_dict = stat._asdict()
                elif not isinstance(stat, dict):
                    stat_dict = dict(zip([col[0] for col in cursor.description], stat))
                else:
                    stat_dict = stat
                daily_stats.append(stat_dict)
            
            # Calculate health summary
            if daily_stats:
                trends = analyze_trends(daily_stats)
                recent_stats = daily_stats[:5]
                
                formatted_stats = []
                for stat in recent_stats:
                    stat_date = datetime.strptime(stat['date'], '%Y-%m-%d') if isinstance(stat['date'], str) else stat['date']
                    formatted_stats.append({
                        'date': format_arabic_date(stat_date),
                        'sugar_level': stat['sugar_level'],
                        'blood_pressure': f"{stat['blood_pressure_systolic']}/{stat['blood_pressure_diastolic']}",
                        'sugar_analysis': validate_sugar_level(stat['sugar_level']),
                        'bp_analysis': validate_blood_pressure(stat['blood_pressure_systolic'], stat['blood_pressure_diastolic'])
                    })
                
                health_summary = {
                    'trends': trends,
                    'recent_stats': formatted_stats
                }
        
        # Get medical tests if requested
        if include_tests:
            if current_app.config['DATABASE_URL'].startswith('postgresql://'):
                cursor.execute("""
                    SELECT * FROM medical_tests 
                    WHERE user_id = %s 
                    ORDER BY date DESC 
                    LIMIT 10
                """, (user['id'],))
            else:
                cursor.execute("""
                    SELECT * FROM medical_tests 
                    WHERE user_id = ? 
                    ORDER BY date DESC 
                    LIMIT 10
                """, (user['id'],))
            
            tests_result = cursor.fetchall()
            
            # Convert to list of dicts
            for test in tests_result:
                if hasattr(test, '_asdict'):
                    test_dict = test._asdict()
                elif not isinstance(test, dict):
                    test_dict = dict(zip([col[0] for col in cursor.description], test))
                else:
                    test_dict = test
                medical_tests.append(test_dict)
        
        # Get appointments if requested
        if include_appointments:
            if current_app.config['DATABASE_URL'].startswith('postgresql://'):
                cursor.execute("""
                    SELECT * FROM appointments 
                    WHERE user_id = %s 
                    ORDER BY date DESC 
                    LIMIT 10
                """, (user['id'],))
            else:
                cursor.execute("""
                    SELECT * FROM appointments 
                    WHERE user_id = ? 
                    ORDER BY date DESC 
                    LIMIT 10
                """, (user['id'],))
            
            appointments_result = cursor.fetchall()
            
            # Convert to list of dicts
            for apt in appointments_result:
                if hasattr(apt, '_asdict'):
                    apt_dict = apt._asdict()
                elif not isinstance(apt, dict):
                    apt_dict = dict(zip([col[0] for col in cursor.description], apt))
                else:
                    apt_dict = apt
                appointments.append(apt_dict)
        
        # Get recipes if requested
        if include_recipes:
            if current_app.config['DATABASE_URL'].startswith('postgresql://'):
                cursor.execute("""
                    SELECT * FROM recipes 
                    WHERE author_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT 5
                """, (user['id'],))
            else:
                cursor.execute("""
                    SELECT * FROM recipes 
                    WHERE author_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT 5
                """, (user['id'],))
            
            recipes_result = cursor.fetchall()
            
            # Convert to list of dicts
            for recipe in recipes_result:
                if hasattr(recipe, '_asdict'):
                    recipe_dict = recipe._asdict()
                elif not isinstance(recipe, dict):
                    recipe_dict = dict(zip([col[0] for col in cursor.description], recipe))
                else:
                    recipe_dict = recipe
                recipes.append(recipe_dict)
        
        cursor.close()
        
        # Generate report data
        report_date = format_arabic_date(datetime.utcnow())
        report_id = f"RPT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        report_data = {
            'report_id': report_id,
            'title': title,
            'generated_at': datetime.utcnow().isoformat(),
            'generated_at_arabic': report_date,
            'patient': {
                'id': profile['id'],
                'name': f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip(),
                'username': profile.get('username', ''),
                'email': profile.get('email', ''),
                'age': profile.get('age'),
                'height': profile.get('height'),
                'weight': profile.get('weight'),
                'gender': profile.get('gender'),
                'diseases': profile.get('diseases'),
                'allergies': profile.get('allergies'),
                'medications': profile.get('medications')
            },
            'summary': health_summary,
            'statistics': {
                'total_records': len(daily_stats),
                'data': []
            } if include_stats and daily_stats else None,
            'medical_tests': {
                'total_tests': len(medical_tests),
                'data': []
            } if include_tests and medical_tests else None,
            'appointments': {
                'total_appointments': len(appointments),
                'upcoming': 0,
                'data': []
            } if include_appointments and appointments else None,
            'recipes': {
                'total_recipes': len(recipes),
                'data': recipes
            } if include_recipes and recipes else None,
            'recommendations': {
                'nutrition': [
                    "تناول وجبات متوازنة تحتوي على جميع العناصر الغذائية",
                    "تقليل السكريات والدهون المشبعة",
                    "زيادة تناول الألياف من الخضروات والفواكه",
                    "شرب 8-10 أكواب من الماء يومياً"
                ],
                'exercise': [
                    "ممارسة 30 دقيقة من الرياضة المعتدلة يومياً",
                    "المشي السريع لمدة 20-30 دقيقة",
                    "تمارين الإطالة والمرونة",
                    "استشارة الطبيب قبل البدء بأي برنامج رياضي جديد"
                ],
                'monitoring': [
                    "القياس الدوري لمستوى السكر والضغط",
                    "تسجيل النتائج في التطبيق بشكل منتظم",
                    "متابعة الطبيب بانتظام",
                    "الالتزام بالعلاج الموصوف"
                ]
            }
        }
        
        # Format statistics data
        if report_data['statistics'] and daily_stats:
            for stat in daily_stats[:10]:
                stat_date = datetime.strptime(stat['date'], '%Y-%m-%d') if isinstance(stat['date'], str) else stat['date']
                report_data['statistics']['data'].append({
                    **stat,
                    'formatted_date': format_arabic_date(stat_date),
                    'sugar_analysis': validate_sugar_level(stat['sugar_level']),
                    'bp_analysis': validate_blood_pressure(stat['blood_pressure_systolic'], stat['blood_pressure_diastolic'])
                })
        
        # Format medical tests data
        if report_data['medical_tests'] and medical_tests:
            for test in medical_tests:
                test_date = datetime.strptime(test['date'], '%Y-%m-%d') if isinstance(test['date'], str) else test['date']
                report_data['medical_tests']['data'].append({
                    **test,
                    'formatted_date': format_arabic_date(test_date),
                    'formatted_time': test.get('time', '')[:5] if test.get('time') else ''
                })
        
        # Format appointments data
        if report_data['appointments'] and appointments:
            now = datetime.utcnow()
            for apt in appointments:
                apt_date_str = apt['date']
                if apt.get('time'):
                    apt_date_str = f"{apt['date']}T{apt['time']}"
                
                apt_date = datetime.fromisoformat(apt_date_str.replace('Z', '+00:00')) if 'T' in apt_date_str else datetime.strptime(apt['date'], '%Y-%m-%d')
                
                is_upcoming = apt_date >= now
                if is_upcoming:
                    report_data['appointments']['upcoming'] += 1
                
                report_data['appointments']['data'].append({
                    **apt,
                    'formatted_date': format_arabic_date(apt_date),
                    'formatted_time': apt.get('time', '')[:5] if apt.get('time') else '',
                    'status': 'upcoming' if is_upcoming else 'past'
                })
        
        return jsonify({
            'success': True,
            'message': "تم إنشاء التقرير بنجاح",
            'data': report_data
        })
        
    except Exception as error:
        print(f'Generate report error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء إنشاء التقرير"
        }), 500

# Generate MODERN HTML report
@reports_bp.route('/health/html', methods=['GET'])
@auth_middleware
@error_handler
def generate_html_report():
    try:
        user = g.user
        
        # Parse query parameters
        title = request.args.get('title', 'التقرير الصحي الشامل')
        include_recipes = request.args.get('include_recipes', 'false').lower() == 'true'
        include_stats = request.args.get('include_stats', 'true').lower() != 'false'
        include_tests = request.args.get('include_tests', 'true').lower() != 'false'
        include_appointments = request.args.get('include_appointments', 'true').lower() != 'false'
        theme = request.args.get('theme', 'medical')
        animated = request.args.get('animated', 'true').lower() != 'false'
        
        db = get_db()
        cursor = db.cursor()
        
        # Get user profile
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
        
        profile_result = cursor.fetchone()
        
        if not profile_result:
            cursor.close()
            return jsonify({
                'success': False,
                'error': "المستخدم غير موجود"
            }), 404
        
        # Convert profile to dict
        if hasattr(profile_result, '_asdict'):
            profile = profile_result._asdict()
        elif not isinstance(profile_result, dict):
            profile = dict(zip([col[0] for col in cursor.description], profile_result))
        else:
            profile = profile_result
        
        # Initialize data objects
        daily_stats = []
        medical_tests = []
        appointments = []
        health_indicators = {}
        
        # Get data if requested
        if include_stats:
            if current_app.config['DATABASE_URL'].startswith('postgresql://'):
                cursor.execute("""
                    SELECT * FROM daily_stats 
                    WHERE user_id = %s 
                    ORDER BY date DESC 
                    LIMIT 15
                """, (user['id'],))
            else:
                cursor.execute("""
                    SELECT * FROM daily_stats 
                    WHERE user_id = ? 
                    ORDER BY date DESC 
                    LIMIT 15
                """, (user['id'],))
            
            stats_result = cursor.fetchall()
            
            # Convert to list of dicts
            for stat in stats_result:
                if hasattr(stat, '_asdict'):
                    stat_dict = stat._asdict()
                elif not isinstance(stat, dict):
                    stat_dict = dict(zip([col[0] for col in cursor.description], stat))
                else:
                    stat_dict = stat
                daily_stats.append(stat_dict)
            
            # Calculate averages for health indicators
            if daily_stats:
                total_sugar = sum(stat['sugar_level'] for stat in daily_stats)
                total_systolic = sum(stat['blood_pressure_systolic'] for stat in daily_stats)
                total_diastolic = sum(stat['blood_pressure_diastolic'] for stat in daily_stats)
                
                health_indicators = {
                    'avg_sugar': round(total_sugar / len(daily_stats)),
                    'avg_systolic': round(total_systolic / len(daily_stats)),
                    'avg_diastolic': round(total_diastolic / len(daily_stats)),
                    'total_measurements': len(daily_stats)
                }
        
        if include_tests:
            if current_app.config['DATABASE_URL'].startswith('postgresql://'):
                cursor.execute("""
                    SELECT * FROM medical_tests 
                    WHERE user_id = %s 
                    ORDER BY date DESC 
                    LIMIT 8
                """, (user['id'],))
            else:
                cursor.execute("""
                    SELECT * FROM medical_tests 
                    WHERE user_id = ? 
                    ORDER BY date DESC 
                    LIMIT 8
                """, (user['id'],))
            
            tests_result = cursor.fetchall()
            
            # Convert to list of dicts
            for test in tests_result:
                if hasattr(test, '_asdict'):
                    test_dict = test._asdict()
                elif not isinstance(test, dict):
                    test_dict = dict(zip([col[0] for col in cursor.description], test))
                else:
                    test_dict = test
                medical_tests.append(test_dict)
        
        if include_appointments:
            if current_app.config['DATABASE_URL'].startswith('postgresql://'):
                cursor.execute("""
                    SELECT * FROM appointments 
                    WHERE user_id = %s 
                    ORDER BY date DESC 
                    LIMIT 6
                """, (user['id'],))
            else:
                cursor.execute("""
                    SELECT * FROM appointments 
                    WHERE user_id = ? 
                    ORDER BY date DESC 
                    LIMIT 6
                """, (user['id'],))
            
            appointments_result = cursor.fetchall()
            
            # Convert to list of dicts
            for apt in appointments_result:
                if hasattr(apt, '_asdict'):
                    apt_dict = apt._asdict()
                elif not isinstance(apt, dict):
                    apt_dict = dict(zip([col[0] for col in cursor.description], apt))
                else:
                    apt_dict = apt
                appointments.append(apt_dict)
        
        cursor.close()
        
        # Generate report data
        report_date = format_arabic_date(datetime.utcnow())
        report_id = f"RPT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        # Theme configurations
        themes = {
            'medical': {
                'primary': '#10b981',
                'secondary': '#3b82f6',
                'accent': '#8b5cf6',
                'background': '#f8fafc',
                'card': '#ffffff',
                'text': '#1e293b'
            },
            'modern': {
                'primary': '#6366f1',
                'secondary': '#8b5cf6',
                'accent': '#ec4899',
                'background': '#f8fafc',
                'card': '#ffffff',
                'text': '#1e293b'
            },
            'dark': {
                'primary': '#10b981',
                'secondary': '#3b82f6',
                'accent': '#8b5cf6',
                'background': '#0f172a',
                'card': '#1e293b',
                'text': '#f1f5f9'
            }
        }
        
        theme_colors = themes.get(theme, themes['medical'])
        animation_class = 'animate-on-scroll' if animated else ''
        
        # Generate the full HTML report
        # This is a simplified version - you can expand it with the full HTML from your Hono code
        html = f"""
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - عشبة شفاء</title>
    <style>
        :root {{
            --primary: {theme_colors['primary']};
            --secondary: {theme_colors['secondary']};
            --accent: {theme_colors['accent']};
            --background: {theme_colors['background']};
            --card: {theme_colors['card']};
            --text: {theme_colors['text']};
        }}
        
        body {{
            font-family: 'Tajawal', sans-serif;
            background: var(--background);
            color: var(--text);
            padding: 20px;
        }}
        
        .report-container {{
            max-width: 1200px;
            margin: 0 auto;
            background: var(--card);
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        .report-header {{
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: white;
            padding: 40px;
            text-align: center;
        }}
        
        .report-title {{
            font-size: 32px;
            margin-bottom: 10px;
        }}
        
        .patient-info {{
            padding: 30px;
        }}
        
        .section-title {{
            color: var(--primary);
            border-bottom: 2px solid var(--primary);
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .info-card {{
            background: var(--card);
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }}
        
        .info-label {{
            color: #6b7280;
            font-size: 14px;
            margin-bottom: 5px;
        }}
        
        .info-value {{
            font-size: 18px;
            font-weight: 600;
        }}
        
        @media print {{
            .no-print {{ display: none !important; }}
            body {{ background: white !important; }}
            .report-container {{ box-shadow: none !important; margin: 0 !important; }}
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="report-header">
            <h1 class="report-title">{title}</h1>
            <p>تم إنشاء التقرير في {report_date}</p>
            <p>رقم التقرير: {report_id}</p>
        </div>
        
        <div class="patient-info">
            <h2 class="section-title">المعلومات الشخصية</h2>
            <div class="info-grid">
                <div class="info-card">
                    <div class="info-label">الاسم الكامل</div>
                    <div class="info-value">{profile.get('first_name', '')} {profile.get('last_name', '')}</div>
                </div>
                <div class="info-card">
                    <div class="info-label">البريد الإلكتروني</div>
                    <div class="info-value">{profile.get('email', '')}</div>
                </div>
                <div class="info-card">
                    <div class="info-label">اسم المستخدم</div>
                    <div class="info-value">{profile.get('username', '')}</div>
                </div>
                {f'<div class="info-card"><div class="info-label">العمر</div><div class="info-value">{profile.get("age", "")} سنة</div></div>' if profile.get('age') else ''}
                {f'<div class="info-card"><div class="info-label">النوع</div><div class="info-value">{"ذكر" if profile.get("gender") == "male" else "أنثى"}</div></div>' if profile.get('gender') else ''}
            </div>
            
            {f'<h2 class="section-title">المعلومات الصحية</h2><div class="info-grid">' + 
             (f'<div class="info-card"><div class="info-label">الأمراض المزمنة</div><div class="info-value">{profile.get("diseases", "")}</div></div>' if profile.get('diseases') else '') +
             (f'<div class="info-card"><div class="info-label">الحساسية</div><div class="info-value">{profile.get("allergies", "")}</div></div>' if profile.get('allergies') else '') +
             (f'<div class="info-card"><div class="info-label">الأدوية</div><div class="info-value">{profile.get("medications", "")}</div></div>' if profile.get('medications') else '') + '</div>' 
             if any([profile.get('diseases'), profile.get('allergies'), profile.get('medications')]) else ''}
            
            {f'''<h2 class="section-title">المؤشرات الصحية</h2>
<div class="info-grid">
    <div class="info-card">
        <div class="info-label">متوسط مستوى السكر</div>
        <div class="info-value">{health_indicators.get('avg_sugar', 0)}</div>
    </div>
    <div class="info-card">
        <div class="info-label">متوسط ضغط الدم</div>
        <div class="info-value">{health_indicators.get('avg_systolic', 0)}/{health_indicators.get('avg_diastolic', 0)}</div>
    </div>
    <div class="info-card">
        <div class="info-label">عدد القياسات</div>
        <div class="info-value">{health_indicators.get('total_measurements', 0)}</div>
    </div>
</div>''' if health_indicators else ''}
        </div>
        
        <div style="text-align: center; padding: 30px; color: #6b7280;">
            <p>تم إنشاء هذا التقرير بواسطة نظام عشبة شفاء للرعاية الصحية الذكية</p>
            <p>جميع الحقوق محفوظة © {datetime.utcnow().year} - عشبة شفاء</p>
            <button class="no-print" onclick="window.print()" style="
                background: var(--primary);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                margin-top: 20px;
            ">
                طباعة التقرير
            </button>
        </div>
    </div>
</body>
</html>
        """
        
        return html
        
    except Exception as error:
        print(f'Generate HTML report error: {error}')
        return jsonify({
            'success': False,
            'error': "حدث خطأ أثناء إنشاء التقرير"
        }), 500