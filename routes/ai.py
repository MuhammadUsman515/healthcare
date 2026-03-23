from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from models import db, Patient, MedicalRecord, Appointment, Bill
from datetime import datetime, timedelta
from sqlalchemy import func

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')

# ─── Symptom → Condition knowledge base ──────────────────────────────────────
SYMPTOM_DB = {
    'fever': ['Malaria', 'Typhoid', 'Influenza', 'COVID-19', 'Dengue Fever', 'Urinary Tract Infection'],
    'headache': ['Migraine', 'Tension Headache', 'Hypertension', 'Sinusitis', 'Cluster Headache'],
    'cough': ['Common Cold', 'Bronchitis', 'Asthma', 'Pneumonia', 'Tuberculosis', 'COVID-19'],
    'chest pain': ['Angina', 'Myocardial Infarction', 'Pleuritis', 'GERD', 'Musculoskeletal Pain'],
    'abdominal pain': ['Appendicitis', 'Gastritis', 'Peptic Ulcer', 'IBS', 'Kidney Stone', 'Pancreatitis'],
    'shortness of breath': ['Asthma', 'Heart Failure', 'Anemia', 'Pneumonia', 'Pulmonary Embolism'],
    'fatigue': ['Anemia', 'Diabetes', 'Hypothyroidism', 'Depression', 'Chronic Fatigue Syndrome'],
    'nausea': ['Gastroenteritis', 'Food Poisoning', 'GERD', 'Pregnancy', 'Migraine'],
    'vomiting': ['Gastroenteritis', 'Food Poisoning', 'Appendicitis', 'Migraine', 'Intestinal Obstruction'],
    'diarrhea': ['Gastroenteritis', 'Food Poisoning', 'IBS', 'Crohn\'s Disease', 'Cholera'],
    'dizziness': ['Hypertension', 'Anemia', 'Inner Ear Disorder', 'Hypoglycemia', 'Vertigo'],
    'back pain': ['Lumbar Strain', 'Herniated Disc', 'Kidney Infection', 'Osteoporosis', 'Spondylitis'],
    'joint pain': ['Arthritis', 'Gout', 'Lupus', 'Rheumatoid Arthritis', 'Fibromyalgia'],
    'rash': ['Eczema', 'Psoriasis', 'Allergic Reaction', 'Measles', 'Chickenpox', 'Dermatitis'],
    'sore throat': ['Strep Throat', 'Tonsillitis', 'Common Cold', 'Influenza', 'Mono'],
    'runny nose': ['Common Cold', 'Allergic Rhinitis', 'Influenza', 'Sinusitis'],
    'urination pain': ['Urinary Tract Infection', 'Kidney Stone', 'Prostatitis', 'STI'],
    'weight loss': ['Diabetes', 'Hyperthyroidism', 'Cancer', 'Tuberculosis', 'Crohn\'s Disease'],
    'blurred vision': ['Diabetes', 'Hypertension', 'Cataracts', 'Glaucoma', 'Migraine'],
    'swelling': ['Heart Failure', 'Kidney Disease', 'DVT', 'Cellulitis', 'Allergic Reaction'],
}

DRUG_INTERACTIONS = {
    ('warfarin', 'aspirin'): {'severity': 'High', 'effect': 'Increased bleeding risk. Avoid combination.'},
    ('warfarin', 'ibuprofen'): {'severity': 'High', 'effect': 'Significantly increases anticoagulant effect and bleeding risk.'},
    ('metformin', 'alcohol'): {'severity': 'Moderate', 'effect': 'Increased risk of lactic acidosis.'},
    ('ssri', 'maoi'): {'severity': 'Critical', 'effect': 'Serotonin syndrome — potentially life-threatening. Do NOT combine.'},
    ('statins', 'clarithromycin'): {'severity': 'High', 'effect': 'Increased risk of myopathy and rhabdomyolysis.'},
    ('ace inhibitor', 'potassium'): {'severity': 'Moderate', 'effect': 'Risk of hyperkalemia (elevated potassium).'},
    ('digoxin', 'amiodarone'): {'severity': 'High', 'effect': 'Digoxin toxicity risk — monitor levels.'},
    ('methotrexate', 'nsaids'): {'severity': 'High', 'effect': 'NSAIDs reduce methotrexate clearance — toxicity risk.'},
    ('sildenafil', 'nitrates'): {'severity': 'Critical', 'effect': 'Severe hypotension. Absolutely contraindicated.'},
    ('clopidogrel', 'omeprazole'): {'severity': 'Moderate', 'effect': 'Omeprazole reduces antiplatelet effect of clopidogrel.'},
    ('lithium', 'nsaids'): {'severity': 'High', 'effect': 'NSAIDs increase lithium levels — toxicity risk.'},
    ('fluoroquinolones', 'antacids'): {'severity': 'Moderate', 'effect': 'Antacids reduce fluoroquinolone absorption by up to 90%.'},
}

RISK_FACTORS = {
    'diabetes': 20,
    'hypertension': 15,
    'heart disease': 25,
    'obesity': 10,
    'smoking': 15,
    'asthma': 10,
    'copd': 20,
    'kidney disease': 25,
    'cancer': 30,
    'stroke': 25,
}


def check_drug_interactions(drugs):
    """Check for drug interactions in a list of drug names."""
    results = []
    drugs_lower = [d.lower().strip() for d in drugs if d.strip()]

    for (drug_a, drug_b), info in DRUG_INTERACTIONS.items():
        a_match = any(drug_a in d or d in drug_a for d in drugs_lower)
        b_match = any(drug_b in d or d in drug_b for d in drugs_lower)
        if a_match and b_match:
            results.append({
                'drug_a': drug_a.title(),
                'drug_b': drug_b.title(),
                'severity': info['severity'],
                'effect': info['effect'],
            })
    return results


def calculate_risk_score(patient):
    """Calculate a simple risk score for a patient based on chronic conditions."""
    score = 0
    conditions = (patient.chronic_conditions or '').lower()
    for condition, weight in RISK_FACTORS.items():
        if condition in conditions:
            score += weight
    # Age factor
    try:
        age = patient.age
        if age > 70:
            score += 25
        elif age > 60:
            score += 15
        elif age > 50:
            score += 10
        elif age > 40:
            score += 5
    except Exception:
        pass
    return min(100, score)


@ai_bp.route('/')
@login_required
def index():
    return render_template('ai/index.html')


@ai_bp.route('/symptom-checker', methods=['GET', 'POST'])
@login_required
def symptom_checker():
    results = []
    selected_symptoms = []
    if request.method == 'POST':
        selected_symptoms = request.form.getlist('symptoms')
        custom = request.form.get('custom_symptoms', '')
        if custom:
            for s in custom.split(','):
                s = s.strip().lower()
                if s:
                    selected_symptoms.append(s)

        condition_scores = {}
        for symptom in selected_symptoms:
            for key, conditions in SYMPTOM_DB.items():
                if key in symptom or symptom in key:
                    for c in conditions:
                        condition_scores[c] = condition_scores.get(c, 0) + 1

        # Sort by score
        sorted_conditions = sorted(condition_scores.items(), key=lambda x: x[1], reverse=True)
        results = [
            {
                'condition': cond,
                'confidence': min(95, int((score / len(selected_symptoms)) * 100)) if selected_symptoms else 50,
                'score': score,
            }
            for cond, score in sorted_conditions[:8]
        ]

    return render_template('ai/symptom_checker.html',
                           symptoms=list(SYMPTOM_DB.keys()),
                           results=results,
                           selected_symptoms=selected_symptoms)


@ai_bp.route('/drug-checker', methods=['GET', 'POST'])
@login_required
def drug_checker():
    interactions = []
    drugs_input = ''
    if request.method == 'POST':
        drugs_input = request.form.get('drugs', '')
        drugs = [d.strip() for d in drugs_input.split(',') if d.strip()]
        interactions = check_drug_interactions(drugs)

    return render_template('ai/drug_checker.html',
                           interactions=interactions,
                           drugs_input=drugs_input)


@ai_bp.route('/risk-score/<int:patient_id>')
@login_required
def risk_score(patient_id):
    from models import Patient
    patient = Patient.query.get_or_404(patient_id)
    score = calculate_risk_score(patient)
    level = 'low' if score < 30 else 'medium' if score < 60 else 'high'
    return jsonify({
        'patient': patient.full_name,
        'score': score,
        'level': level,
        'factors': [c for c in RISK_FACTORS if c in (patient.chronic_conditions or '').lower()],
    })


@ai_bp.route('/insights')
@login_required
def insights():
    """Generate AI-powered insights from the HMS data."""
    from models import Patient, Appointment, Bill, OPDQueue

    today = datetime.utcnow().date()
    last_30 = today - timedelta(days=30)

    # Appointment trend (last 7 days)
    appt_trend = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        count = Appointment.query.filter(
            func.date(Appointment.appointment_date) == day
        ).count()
        appt_trend.append({'date': day.strftime('%d %b'), 'count': count})

    # Revenue trend (last 6 months)
    revenue_trend = []
    for i in range(5, -1, -1):
        m = today.replace(day=1) - timedelta(days=i * 30)
        total = db.session.query(func.sum(Bill.total_amount)).filter(
            func.extract('month', Bill.bill_date) == m.month,
            func.extract('year', Bill.bill_date) == m.year,
        ).scalar() or 0
        revenue_trend.append({'month': m.strftime('%b %Y'), 'amount': float(total)})

    # Top diagnoses
    diagnoses = db.session.query(
        MedicalRecord.diagnosis,
        func.count(MedicalRecord.id).label('count')
    ).filter(
        MedicalRecord.diagnosis.isnot(None),
        MedicalRecord.diagnosis != ''
    ).group_by(MedicalRecord.diagnosis).order_by(func.count(MedicalRecord.id).desc()).limit(5).all()

    # Busiest days
    from sqlalchemy import extract
    busy_days = db.session.query(
        func.strftime('%w', Appointment.appointment_date).label('dow'),
        func.count(Appointment.id).label('count')
    ).group_by('dow').all()

    day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    busy = {day_names[int(d.dow)]: d.count for d in busy_days if d.dow}

    ai_insights = []

    # Insight 1: Peak day
    if busy:
        peak_day = max(busy, key=busy.get)
        ai_insights.append({
            'icon': 'calendar-alt',
            'color': 'primary',
            'title': f'Peak Day: {peak_day}',
            'body': f'{peak_day} has the most appointments. Consider adding extra staff on this day.',
        })

    # Insight 2: Revenue trend
    if len(revenue_trend) >= 2:
        last = revenue_trend[-1]['amount']
        prev = revenue_trend[-2]['amount']
        if last > prev:
            pct = ((last - prev) / prev * 100) if prev > 0 else 100
            ai_insights.append({
                'icon': 'chart-line',
                'color': 'success',
                'title': f'Revenue up {pct:.0f}% this month',
                'body': 'Great momentum! Revenue is growing compared to last month.',
            })
        else:
            pct = ((prev - last) / prev * 100) if prev > 0 else 0
            ai_insights.append({
                'icon': 'chart-line',
                'color': 'warning',
                'title': f'Revenue down {pct:.0f}% this month',
                'body': 'Revenue has dipped. Consider reviewing billing or patient volume.',
            })

    # Insight 3: High-risk patient count
    patients = Patient.query.filter_by(status='active').all()
    high_risk = sum(1 for p in patients if calculate_risk_score(p) >= 60)
    if high_risk > 0:
        ai_insights.append({
            'icon': 'exclamation-triangle',
            'color': 'danger',
            'title': f'{high_risk} High-Risk Patient{"s" if high_risk > 1 else ""}',
            'body': 'These patients have chronic conditions or age factors requiring extra attention.',
        })

    # Insight 4: OPD wait analysis
    avg_wait = 25  # mock avg
    if avg_wait > 20:
        ai_insights.append({
            'icon': 'clock',
            'color': 'warning',
            'title': 'OPD Wait Time Alert',
            'body': f'Average OPD wait is ~{avg_wait} min. Consider staggered scheduling.',
        })

    return render_template('ai/insights.html',
                           appt_trend=appt_trend,
                           revenue_trend=revenue_trend,
                           diagnoses=diagnoses,
                           ai_insights=ai_insights,
                           high_risk_count=high_risk)
