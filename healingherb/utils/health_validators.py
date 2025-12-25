def validate_blood_pressure(systolic: int, diastolic: int) -> dict:
    """Validate blood pressure readings"""
    if systolic < 120 and diastolic < 80:
        return {
            'category': 'طبيعي',
            'status': 'good',
            'message': 'ضغط الدم في النطاق الطبيعي. استمر في المتابعة.'
        }
    elif (systolic >= 120 and systolic <= 129) and diastolic < 80:
        return {
            'category': 'مرتفع قليلاً',
            'status': 'warning',
            'message': 'ضغط الدم مرتفع قليلاً. راقب الأعراض واستشر الطبيب.'
        }
    elif (systolic >= 130 and systolic <= 139) or (diastolic >= 80 and diastolic <= 89):
        return {
            'category': 'مرتفع (المرحلة 1)',
            'status': 'danger',
            'message': 'ضغط الدم مرتفع. راجع الطبيب قريبًا.'
        }
    elif (systolic >= 140 and systolic <= 179) or (diastolic >= 90 and diastolic <= 119):
        return {
            'category': 'مرتفع (المرحلة 2)',
            'status': 'critical',
            'message': 'ضغط الدم مرتفع بشكل خطير. راجع الطبيب فورًا.'
        }
    else:
        return {
            'category': 'أزمة ارتفاع ضغط',
            'status': 'emergency',
            'message': 'حالة طارئة! توجه إلى أقرب مستشفى أو اتصل بالإسعاف.'
        }

def validate_sugar_level(sugar: float) -> dict:
    """Validate blood sugar level"""
    if sugar < 100:
        return {
            'category': 'طبيعي',
            'status': 'good',
            'message': 'مستوى السكر طبيعي. استمر في النظام الغذائي الصحي.'
        }
    elif sugar >= 100 and sugar < 126:
        return {
            'category': 'مرتفع قليلاً',
            'status': 'warning',
            'message': 'مستوى السكر مرتفع قليلاً. راقب الأعراض وراجع الطبيب.'
        }
    else:
        return {
            'category': 'مرتفع',
            'status': 'danger',
            'message': 'مستوى السكر مرتفع. راجع الطبيب لضبط العلاج.'
        }

def analyze_trends(stats: list) -> dict:
    """Analyze health trends from stats"""
    if len(stats) < 2:
        return {
            'sugar_trend': 'stable',
            'bp_trend': 'stable',
            'message': 'لا توجد بيانات كافية لتحليل الاتجاهات'
        }
    
    recent_stats = stats[:min(10, len(stats))]
    
    # Calculate sugar trend
    sugar_changes = []
    for i in range(1, len(recent_stats)):
        change = recent_stats[i-1]['sugar_level'] - recent_stats[i]['sugar_level']
        sugar_changes.append(change)
    
    avg_sugar_change = sum(sugar_changes) / len(sugar_changes) if sugar_changes else 0
    
    # Calculate BP trend
    bp_changes = []
    for i in range(1, len(recent_stats)):
        bp1 = (recent_stats[i-1]['blood_pressure_systolic'] + recent_stats[i-1]['blood_pressure_diastolic']) / 2
        bp2 = (recent_stats[i]['blood_pressure_systolic'] + recent_stats[i]['blood_pressure_diastolic']) / 2
        bp_changes.append(bp1 - bp2)
    
    avg_bp_change = sum(bp_changes) / len(bp_changes) if bp_changes else 0
    
    # Determine trends
    sugar_trend = 'improving' if avg_sugar_change > 5 else 'worsening' if avg_sugar_change < -5 else 'stable'
    bp_trend = 'improving' if avg_bp_change > 5 else 'worsening' if avg_bp_change < -5 else 'stable'
    
    return {
        'sugar_trend': sugar_trend,
        'bp_trend': bp_trend,
        'avg_sugar_change': round(avg_sugar_change, 1),
        'avg_bp_change': round(avg_bp_change, 1),
        'message': f'الاتجاه: السكر {sugar_trend}، الضغط {bp_trend}'
    }

def calculate_bmi(height: float, weight: float) -> float:
    """Calculate BMI"""
    if height <= 0:
        return 0
    height_m = height / 100
    return weight / (height_m * height_m)

def get_bmi_category(bmi: float) -> str:
    """Get BMI category in Arabic"""
    if bmi < 18.5:
        return 'نقص الوزن'
    elif bmi < 25:
        return 'وزن طبيعي'
    elif bmi < 30:
        return 'زيادة في الوزن'
    else:
        return 'سمنة'