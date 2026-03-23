from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import (db, Patient, MedicalRecord, Appointment, Bill, BillItem,
                    Doctor, LabTest, Admission, OPDQueue, Prescription,
                    BloodRequest, BloodInventory, Staff, Ward, Bed)
from datetime import datetime, date, timedelta
from sqlalchemy import func, or_

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


# ─── Triage Assistant ─────────────────────────────────────────────────────────
TRIAGE_RULES = [
    # (keywords, severity, label, action, color)
    (['chest pain', 'chest tightness', 'heart attack', 'mi', 'cardiac'],
     'critical', 'CRITICAL', 'Immediate resuscitation — call code team NOW', 'danger'),
    (['stroke', 'facial droop', 'arm weakness', 'speech slur', 'unconscious', 'unresponsive', 'seizure'],
     'critical', 'CRITICAL', 'Activate stroke/neuro protocol immediately', 'danger'),
    (['shortness of breath', 'breathing difficulty', 'respiratory distress', 'spo2 low', 'oxygen'],
     'critical', 'CRITICAL', 'Immediate O₂ support + physician assessment', 'danger'),
    (['high fever', 'fever above 40', 'fever 40', 'sepsis', 'septic'],
     'urgent', 'URGENT', 'Start IV access, blood cultures, antibiotics within 1 hr', 'warning'),
    (['severe pain', 'pain score 8', 'pain score 9', 'pain score 10', 'trauma', 'fracture', 'bleeding'],
     'urgent', 'URGENT', 'Pain management + urgent imaging if needed', 'warning'),
    (['vomiting blood', 'blood in stool', 'hematuria', 'coughing blood'],
     'urgent', 'URGENT', 'IV line, CBC urgent, GI consult', 'warning'),
    (['diabetic', 'hypoglycemia', 'blood sugar low', 'sugar low', 'dizziness', 'syncope'],
     'urgent', 'URGENT', 'BGL check stat, IV dextrose if BGL < 70', 'warning'),
    (['mild fever', 'cough', 'cold', 'sore throat', 'headache', 'body ache', 'rash', 'nausea', 'diarrhea'],
     'routine', 'ROUTINE', 'Standard OPD evaluation — queue as per availability', 'success'),
]

VITALS_ALERTS = [
    ('hr', 'Heart Rate', 60, 100, 'bpm', 'Bradycardia', 'Tachycardia'),
    ('sbp', 'Systolic BP', 90, 140, 'mmHg', 'Hypotension', 'Hypertension'),
    ('dbp', 'Diastolic BP', 60, 90, 'mmHg', 'Low Diastolic', 'High Diastolic'),
    ('spo2', 'SpO₂', 95, 100, '%', 'Hypoxia', None),
    ('rr', 'Resp Rate', 12, 20, '/min', 'Bradypnea', 'Tachypnea'),
    ('temp', 'Temperature', 36.0, 37.5, '°C', 'Hypothermia', 'Fever'),
]


@ai_bp.route('/triage', methods=['GET', 'POST'])
@login_required
def triage():
    result = None
    if request.method == 'POST':
        chief = request.form.get('chief_complaint', '').lower()
        hr = request.form.get('hr', '')
        sbp = request.form.get('sbp', '')
        dbp = request.form.get('dbp', '')
        spo2 = request.form.get('spo2', '')
        rr = request.form.get('rr', '')
        temp = request.form.get('temp', '')

        # Vitals alerts
        vitals_flags = []
        vals = {'hr': hr, 'sbp': sbp, 'dbp': dbp, 'spo2': spo2, 'rr': rr, 'temp': temp}
        for key, label, low, high, unit, low_name, high_name in VITALS_ALERTS:
            try:
                v = float(vals[key])
                if v < low:
                    vitals_flags.append({'label': label, 'value': f'{v} {unit}', 'flag': low_name, 'color': 'danger'})
                elif high_name and v > high:
                    vitals_flags.append({'label': label, 'value': f'{v} {unit}', 'flag': high_name, 'color': 'warning'})
            except (ValueError, TypeError):
                pass

        # Auto-upgrade severity if vitals are critical
        vitals_critical = any(
            f['color'] == 'danger' for f in vitals_flags
        ) or (spo2 and float(spo2) < 90 if spo2 else False)

        # Match triage rules
        severity = 'routine'
        matched_rule = TRIAGE_RULES[-1]  # default routine
        for keywords, sev, label, action, color in TRIAGE_RULES:
            if any(kw in chief for kw in keywords):
                matched_rule = (keywords, sev, label, action, color)
                severity = sev
                break

        if vitals_critical and severity == 'routine':
            severity = 'urgent'
            matched_rule = ([], 'urgent', 'URGENT', 'Abnormal vitals detected — physician review required urgently', 'warning')

        _, sev, label, action, color = matched_rule

        result = {
            'severity': sev,
            'label': label,
            'action': action,
            'color': color,
            'chief': request.form.get('chief_complaint', ''),
            'vitals_flags': vitals_flags,
        }

    patients = Patient.query.filter_by(status='active').order_by(Patient.first_name, Patient.last_name).all()
    return render_template('ai/triage.html', result=result, patients=patients)


# ─── Dose Calculator ──────────────────────────────────────────────────────────
DOSE_DB = {
    'paracetamol': {'adult': '500–1000 mg', 'freq': 'Every 4–6 hrs', 'max': '4000 mg/day', 'pediatric': '10–15 mg/kg', 'pediatric_max': '60 mg/kg/day', 'route': 'PO/IV/PR'},
    'ibuprofen': {'adult': '200–400 mg', 'freq': 'Every 4–6 hrs', 'max': '2400 mg/day', 'pediatric': '5–10 mg/kg', 'pediatric_max': '40 mg/kg/day', 'route': 'PO'},
    'amoxicillin': {'adult': '250–500 mg', 'freq': 'Every 8 hrs', 'max': '3000 mg/day', 'pediatric': '25–45 mg/kg/day', 'pediatric_max': '90 mg/kg/day', 'route': 'PO'},
    'metformin': {'adult': '500–1000 mg', 'freq': 'Twice daily with meals', 'max': '2550 mg/day', 'pediatric': 'Not for children', 'pediatric_max': 'N/A', 'route': 'PO'},
    'omeprazole': {'adult': '20–40 mg', 'freq': 'Once daily (before meals)', 'max': '80 mg/day', 'pediatric': '0.7–3.3 mg/kg', 'pediatric_max': '20 mg/day', 'route': 'PO/IV'},
    'azithromycin': {'adult': '500 mg day 1, 250 mg days 2–5', 'freq': 'Once daily', 'max': '500 mg/day', 'pediatric': '10 mg/kg day 1, 5 mg/kg days 2–5', 'pediatric_max': '500 mg/day', 'route': 'PO'},
    'ciprofloxacin': {'adult': '250–750 mg', 'freq': 'Every 12 hrs', 'max': '1500 mg/day', 'pediatric': 'Use cautiously: 10–20 mg/kg/day', 'pediatric_max': '750 mg/day', 'route': 'PO/IV'},
    'dexamethasone': {'adult': '0.5–9 mg', 'freq': 'Once or divided doses', 'max': '40 mg/day (pulse)', 'pediatric': '0.08–0.3 mg/kg/day', 'pediatric_max': '10 mg/day', 'route': 'PO/IV/IM'},
    'salbutamol': {'adult': '2.5–5 mg', 'freq': 'Every 4–6 hrs nebulization', 'max': '4 puffs PRN', 'pediatric': '2.5 mg (< 5 yr), 5 mg (≥ 5 yr)', 'pediatric_max': 'As directed', 'route': 'INH/NEB'},
    'ondansetron': {'adult': '4–8 mg', 'freq': 'Every 8 hrs', 'max': '24 mg/day', 'pediatric': '0.1 mg/kg (max 4 mg)', 'pediatric_max': '12 mg/day', 'route': 'PO/IV/ODT'},
    'metronidazole': {'adult': '400–500 mg', 'freq': 'Every 8 hrs', 'max': '2000 mg/day', 'pediatric': '7.5 mg/kg/dose', 'pediatric_max': '30 mg/kg/day', 'route': 'PO/IV'},
    'aspirin': {'adult': '75–300 mg (cardiac) / 600–900 mg (pain)', 'freq': 'Once daily (cardiac) / every 4–6 hrs (pain)', 'max': '4000 mg/day', 'pediatric': 'Avoid (Reye syndrome)', 'pediatric_max': 'N/A', 'route': 'PO'},
}


@ai_bp.route('/dose-calculator', methods=['GET', 'POST'])
@login_required
def dose_calculator():
    result = None
    drug = ''
    weight = ''
    age = ''
    if request.method == 'POST':
        drug = request.form.get('drug', '').lower().strip()
        weight = request.form.get('weight', '')
        age = request.form.get('age', '')

        # Find closest match
        matched_drug = None
        matched_key = ''
        for key in DOSE_DB:
            if key in drug or drug in key:
                matched_drug = DOSE_DB[key]
                matched_key = key
                break

        if matched_drug:
            is_pediatric = False
            try:
                if float(age) < 12:
                    is_pediatric = True
            except (ValueError, TypeError):
                pass

            # Calculate dose if weight given
            calc_dose = None
            try:
                w = float(weight)
                if is_pediatric and 'mg/kg' in matched_drug['pediatric']:
                    # Extract first mg/kg value
                    import re
                    nums = re.findall(r'[\d.]+', matched_drug['pediatric'].split('mg/kg')[0])
                    if nums:
                        dose_mg = float(nums[-1]) * w
                        calc_dose = f'{dose_mg:.1f} mg (based on {w} kg × {nums[-1]} mg/kg)'
            except (ValueError, TypeError):
                pass

            result = {
                'drug': matched_key.title(),
                'adult_dose': matched_drug['adult'],
                'freq': matched_drug['freq'],
                'max_dose': matched_drug['max'],
                'pediatric_dose': matched_drug['pediatric'],
                'pediatric_max': matched_drug['pediatric_max'],
                'route': matched_drug['route'],
                'is_pediatric': is_pediatric,
                'calc_dose': calc_dose,
            }
        else:
            result = {'not_found': True, 'drug': drug}

    return render_template('ai/dose_calculator.html',
                           result=result, drug=drug, weight=weight, age=age,
                           drugs=sorted(DOSE_DB.keys()))


# ─── Lab Interpreter ─────────────────────────────────────────────────────────
LAB_NORMALS = {
    # CBC
    'hemoglobin':     {'unit': 'g/dL',      'male': (13.5, 17.5), 'female': (12.0, 15.5), 'group': 'CBC'},
    'hematocrit':     {'unit': '%',          'male': (41, 53),     'female': (36, 46),      'group': 'CBC'},
    'wbc':            {'unit': '×10³/µL',    'both': (4.5, 11.0),                           'group': 'CBC'},
    'platelets':      {'unit': '×10³/µL',    'both': (150, 400),                            'group': 'CBC'},
    'rbc':            {'unit': '×10⁶/µL',    'male': (4.5, 5.5),   'female': (4.0, 5.0),   'group': 'CBC'},
    # Metabolic
    'glucose':        {'unit': 'mg/dL',      'both': (70, 100),                             'group': 'Metabolic', 'note': 'Fasting'},
    'creatinine':     {'unit': 'mg/dL',      'male': (0.7, 1.2),   'female': (0.5, 1.1),   'group': 'Renal'},
    'bun':            {'unit': 'mg/dL',      'both': (7, 20),                               'group': 'Renal'},
    'sodium':         {'unit': 'mEq/L',      'both': (136, 145),                            'group': 'Electrolytes'},
    'potassium':      {'unit': 'mEq/L',      'both': (3.5, 5.0),                            'group': 'Electrolytes'},
    'calcium':        {'unit': 'mg/dL',      'both': (8.5, 10.5),                           'group': 'Electrolytes'},
    'chloride':       {'unit': 'mEq/L',      'both': (98, 107),                             'group': 'Electrolytes'},
    # Liver
    'alt':            {'unit': 'U/L',        'both': (7, 56),                               'group': 'Liver'},
    'ast':            {'unit': 'U/L',        'both': (10, 40),                              'group': 'Liver'},
    'bilirubin':      {'unit': 'mg/dL',      'both': (0.1, 1.2),                            'group': 'Liver'},
    'albumin':        {'unit': 'g/dL',       'both': (3.5, 5.0),                            'group': 'Liver'},
    # Lipids
    'cholesterol':    {'unit': 'mg/dL',      'both': (0, 200),                              'group': 'Lipids', 'note': 'Desirable < 200'},
    'ldl':            {'unit': 'mg/dL',      'both': (0, 100),                              'group': 'Lipids', 'note': 'Optimal < 100'},
    'hdl':            {'unit': 'mg/dL',      'male': (40, 999),    'female': (50, 999),     'group': 'Lipids', 'note': 'Higher is better'},
    'triglycerides':  {'unit': 'mg/dL',      'both': (0, 150),                              'group': 'Lipids'},
    # Thyroid
    'tsh':            {'unit': 'mIU/L',      'both': (0.4, 4.0),                            'group': 'Thyroid'},
    't3':             {'unit': 'ng/dL',      'both': (80, 200),                             'group': 'Thyroid'},
    't4':             {'unit': 'µg/dL',      'both': (5.0, 12.0),                           'group': 'Thyroid'},
    # Other
    'hba1c':          {'unit': '%',          'both': (0, 5.7),                              'group': 'Diabetes', 'note': 'Normal < 5.7%, Pre-DM 5.7–6.4%, DM ≥ 6.5%'},
    'crp':            {'unit': 'mg/L',       'both': (0, 10),                               'group': 'Inflammation', 'note': '< 10 normal, > 10 elevated'},
    'esr':            {'unit': 'mm/hr',      'male': (0, 15),      'female': (0, 20),       'group': 'Inflammation'},
    'uric acid':      {'unit': 'mg/dL',      'male': (3.4, 7.0),   'female': (2.4, 6.0),   'group': 'Metabolic'},
}


@ai_bp.route('/lab-interpreter', methods=['GET', 'POST'])
@login_required
def lab_interpreter():
    results = []
    if request.method == 'POST':
        gender = request.form.get('gender', 'both')
        for key, ref in LAB_NORMALS.items():
            val_str = request.form.get(key, '').strip()
            if not val_str:
                continue
            try:
                val = float(val_str)
            except ValueError:
                continue

            if 'both' in ref:
                low, high = ref['both']
            elif gender == 'male' and 'male' in ref:
                low, high = ref['male']
            elif gender == 'female' and 'female' in ref:
                low, high = ref['female']
            else:
                low, high = ref.get('both', ref.get('male', (0, 999)))

            if val < low:
                status = 'low'
                color = 'danger'
                interp = f'Below normal range ({low}–{high} {ref["unit"]})'
            elif val > high:
                status = 'high'
                color = 'warning'
                interp = f'Above normal range ({low}–{high} {ref["unit"]})'
            else:
                status = 'normal'
                color = 'success'
                interp = f'Within normal range ({low}–{high} {ref["unit"]})'

            results.append({
                'name': key.upper().replace('_', ' '),
                'value': val,
                'unit': ref['unit'],
                'status': status,
                'color': color,
                'interp': interp,
                'group': ref.get('group', 'Other'),
                'note': ref.get('note', ''),
            })

        # Sort: abnormal first
        results.sort(key=lambda x: (x['status'] == 'normal', x['group']))

    return render_template('ai/lab_interpreter.html',
                           lab_normals=LAB_NORMALS, results=results)


# ═══════════════════════════════════════════════════════════════════════════
#  HMS CHATBOT
# ═══════════════════════════════════════════════════════════════════════════

def _find_patients(query_text):
    """Search patients by name or ID from free text."""
    q = query_text.strip()
    results = Patient.query.filter(
        or_(
            Patient.first_name.ilike(f'%{q}%'),
            Patient.last_name.ilike(f'%{q}%'),
            Patient.patient_id.ilike(f'%{q}%'),
            Patient.phone.ilike(f'%{q}%'),
            (Patient.first_name + ' ' + Patient.last_name).ilike(f'%{q}%'),
        )
    ).all()
    return results


def _patient_card(p):
    """Build HTML card for a single patient."""
    risk = calculate_risk_score(p)
    risk_color = 'success' if risk < 30 else 'warning' if risk < 60 else 'danger'
    apts = len(p.appointments)
    bills = p.bills
    outstanding = sum(
        (b.total_amount or 0) - (b.paid_amount or 0) for b in bills
        if b.payment_status in ('unpaid', 'partial')
    )
    return f"""
<div class="bot-card">
  <div class="bot-card-header">
    <span class="avatar-init">{p.full_name[0]}</span>
    <div>
      <div class="fw-bold">{p.full_name}</div>
      <div class="small text-muted">{p.patient_id}</div>
    </div>
    <span class="badge bg-{risk_color} ms-auto">Risk: {risk}%</span>
  </div>
  <div class="bot-card-body">
    <div class="bot-info-grid">
      <div><span class="label">Age</span><span>{p.age}y</span></div>
      <div><span class="label">Gender</span><span>{p.gender or '—'}</span></div>
      <div><span class="label">Blood</span><span class="text-danger fw-bold">{p.blood_group or '—'}</span></div>
      <div><span class="label">Phone</span><span>{p.phone}</span></div>
      <div><span class="label">Status</span><span class="badge bg-{'success' if p.status=='active' else 'secondary'}">{p.status}</span></div>
      <div><span class="label">Appointments</span><span>{apts}</span></div>
    </div>
    {'<div class="bot-alert">⚠️ Conditions: ' + p.chronic_conditions + '</div>' if p.chronic_conditions else ''}
    {'<div class="bot-alert-warn">💊 Allergies: ' + p.allergies + '</div>' if p.allergies else ''}
    {'<div class="bot-alert-danger">💳 Outstanding: PKR {:,.0f}</div>'.format(outstanding) if outstanding > 0 else ''}
  </div>
  <div class="bot-card-footer">
    <a href="/patients/{p.id}" class="bot-link">View Full Profile →</a>
    <a href="/appointments/new?patient_id={p.id}" class="bot-link">+ Book Appointment</a>
  </div>
</div>"""


def _patient_appointments(p):
    apts = Appointment.query.filter_by(patient_id=p.id)\
                            .order_by(Appointment.appointment_date.desc()).limit(5).all()
    if not apts:
        return f"<p>No appointments found for <strong>{p.full_name}</strong>.</p>"
    rows = ""
    for a in apts:
        status_color = {'scheduled':'warning','completed':'success','cancelled':'danger','no-show':'secondary'}.get(a.status,'secondary')
        rows += f"""<tr>
          <td>{a.appointment_date.strftime('%d %b %Y')}</td>
          <td>{a.appointment_time}</td>
          <td>{a.doctor.full_name}</td>
          <td><span class="badge bg-{status_color} {'text-dark' if status_color=='warning' else ''}">{a.status}</span></td>
        </tr>"""
    return f"""
<div class="bot-card">
  <div class="bot-card-header"><span class="avatar-init">{p.full_name[0]}</span>
    <div><div class="fw-bold">{p.full_name} — Appointments</div><div class="small text-muted">Last 5 records</div></div>
  </div>
  <div class="bot-table-wrap">
    <table class="bot-table"><thead><tr><th>Date</th><th>Time</th><th>Doctor</th><th>Status</th></tr></thead>
    <tbody>{rows}</tbody></table>
  </div>
  <div class="bot-card-footer"><a href="/appointments/?patient_id={p.id}" class="bot-link">View All Appointments →</a></div>
</div>"""


def _patient_bills(p):
    bills = Bill.query.filter_by(patient_id=p.id).order_by(Bill.bill_date.desc()).limit(5).all()
    if not bills:
        return f"<p>No billing records for <strong>{p.full_name}</strong>.</p>"
    rows = ""
    total_out = 0
    for b in bills:
        outstanding = (b.total_amount or 0) - (b.paid_amount or 0)
        if b.payment_status in ('unpaid','partial'):
            total_out += outstanding
        rows += f"""<tr>
          <td>{b.bill_number}</td>
          <td>{b.bill_date.strftime('%d %b %Y')}</td>
          <td>PKR {b.total_amount:,.0f}</td>
          <td>PKR {b.paid_amount or 0:,.0f}</td>
          <td><span class="badge bg-{'success' if b.payment_status=='paid' else 'danger' if b.payment_status=='unpaid' else 'warning text-dark'}">{b.payment_status}</span></td>
        </tr>"""
    summary = f'<div class="bot-alert-danger">Total Outstanding: PKR {total_out:,.0f}</div>' if total_out > 0 else '<div class="bot-ok">✅ All bills paid</div>'
    return f"""
<div class="bot-card">
  <div class="bot-card-header"><span class="avatar-init">{p.full_name[0]}</span>
    <div><div class="fw-bold">{p.full_name} — Billing</div></div>
  </div>
  {summary}
  <div class="bot-table-wrap">
    <table class="bot-table"><thead><tr><th>Bill #</th><th>Date</th><th>Total</th><th>Paid</th><th>Status</th></tr></thead>
    <tbody>{rows}</tbody></table>
  </div>
  <div class="bot-card-footer"><a href="/billing/?patient_id={p.id}" class="bot-link">View All Bills →</a></div>
</div>"""


def _patient_labs(p):
    tests = LabTest.query.join(MedicalRecord).filter(MedicalRecord.patient_id == p.id)\
                         .order_by(LabTest.test_date.desc()).limit(8).all()
    if not tests:
        return f"<p>No lab tests found for <strong>{p.full_name}</strong>.</p>"
    rows = ""
    for t in tests:
        rows += f"""<tr>
          <td>{t.test_name}</td>
          <td>{t.test_date.strftime('%d %b %Y') if t.test_date else '—'}</td>
          <td>{(t.result or '—')[:30]}</td>
          <td><span class="badge bg-{'success' if t.status=='completed' else 'warning text-dark'}">{t.status}</span></td>
        </tr>"""
    return f"""
<div class="bot-card">
  <div class="bot-card-header"><span class="avatar-init">{p.full_name[0]}</span>
    <div><div class="fw-bold">{p.full_name} — Lab Tests</div></div>
  </div>
  <div class="bot-table-wrap">
    <table class="bot-table"><thead><tr><th>Test</th><th>Date</th><th>Result</th><th>Status</th></tr></thead>
    <tbody>{rows}</tbody></table>
  </div>
</div>"""


def _patient_records(p):
    records = MedicalRecord.query.filter_by(patient_id=p.id)\
                                 .order_by(MedicalRecord.visit_date.desc()).limit(3).all()
    if not records:
        return f"<p>No medical records for <strong>{p.full_name}</strong>.</p>"
    html = f'<div class="fw-bold mb-2">{p.full_name} — Medical Records</div>'
    for r in records:
        html += f"""<div class="bot-record-card">
          <div class="bot-record-date">{r.visit_date.strftime('%d %b %Y')} · Dr. {r.doctor.full_name if r.doctor else '—'}</div>
          {'<div><strong>Diagnosis:</strong> ' + r.diagnosis + '</div>' if r.diagnosis else ''}
          {'<div><strong>Complaint:</strong> ' + r.chief_complaint + '</div>' if r.chief_complaint else ''}
          {'<div><strong>Treatment:</strong> ' + (r.treatment_plan or '')[:80] + '</div>' if r.treatment_plan else ''}
          <div class="bot-vitals">
            {'<span>BP: ' + r.vitals_bp + '</span>' if r.vitals_bp else ''}
            {'<span>Pulse: ' + r.vitals_pulse + '</span>' if r.vitals_pulse else ''}
            {'<span>Temp: ' + r.vitals_temperature + '°C</span>' if r.vitals_temperature else ''}
            {'<span>O₂: ' + r.vitals_oxygen + '%</span>' if r.vitals_oxygen else ''}
            {'<span>Wt: ' + r.vitals_weight + 'kg</span>' if r.vitals_weight else ''}
          </div>
        </div>"""
    return html


def _today_stats():
    today = date.today()
    apts = Appointment.query.filter_by(appointment_date=today).count()
    scheduled = Appointment.query.filter_by(appointment_date=today, status='scheduled').count()
    completed = Appointment.query.filter_by(appointment_date=today, status='completed').count()
    opd = OPDQueue.query.filter(func.date(OPDQueue.check_in_time) == today).count()
    admitted = Admission.query.filter_by(status='admitted').count()
    pending_labs = LabTest.query.filter_by(status='pending').count()
    total_patients = Patient.query.filter_by(status='active').count()
    return f"""
<div class="bot-stats-grid">
  <div class="bot-stat blue"><div class="num">{apts}</div><div class="lbl">Appointments Today</div></div>
  <div class="bot-stat amber"><div class="num">{scheduled}</div><div class="lbl">Scheduled</div></div>
  <div class="bot-stat green"><div class="num">{completed}</div><div class="lbl">Completed</div></div>
  <div class="bot-stat cyan"><div class="num">{opd}</div><div class="lbl">OPD Patients</div></div>
  <div class="bot-stat purple"><div class="num">{admitted}</div><div class="lbl">Admitted</div></div>
  <div class="bot-stat red"><div class="num">{pending_labs}</div><div class="lbl">Pending Labs</div></div>
  <div class="bot-stat green"><div class="num">{total_patients}</div><div class="lbl">Active Patients</div></div>
</div>
<div class="small text-muted mt-2">📅 {today.strftime('%A, %d %B %Y')}</div>"""


def _hospital_stats():
    total_p = Patient.query.count()
    active_p = Patient.query.filter_by(status='active').count()
    doctors = Doctor.query.filter_by(status='active').count()
    total_beds = Bed.query.count()
    available_beds = Bed.query.filter_by(status='available').count()
    blood_units = db.session.query(func.sum(BloodInventory.units_available)).scalar() or 0
    total_bills = db.session.query(func.sum(Bill.total_amount)).scalar() or 0
    paid = db.session.query(func.sum(Bill.paid_amount)).scalar() or 0
    return f"""
<div class="bot-card">
  <div class="bot-card-header"><span style="font-size:1.5rem">🏥</span>
    <div><div class="fw-bold">Hospital Overview</div></div>
  </div>
  <div class="bot-stats-grid">
    <div class="bot-stat blue"><div class="num">{total_p}</div><div class="lbl">Total Patients</div></div>
    <div class="bot-stat green"><div class="num">{active_p}</div><div class="lbl">Active</div></div>
    <div class="bot-stat purple"><div class="num">{doctors}</div><div class="lbl">Doctors</div></div>
    <div class="bot-stat cyan"><div class="num">{total_beds}</div><div class="lbl">Total Beds</div></div>
    <div class="bot-stat green"><div class="num">{available_beds}</div><div class="lbl">Available Beds</div></div>
    <div class="bot-stat red"><div class="num">{int(blood_units)}</div><div class="lbl">Blood Units</div></div>
    <div class="bot-stat amber"><div class="num">PKR {total_bills/1000:.0f}K</div><div class="lbl">Total Billed</div></div>
    <div class="bot-stat green"><div class="num">PKR {paid/1000:.0f}K</div><div class="lbl">Collected</div></div>
  </div>
</div>"""


def _doctor_info(query_text):
    docs = Doctor.query.filter(
        or_(Doctor.first_name.ilike(f'%{query_text}%'),
            Doctor.last_name.ilike(f'%{query_text}%'),
            Doctor.specialization.ilike(f'%{query_text}%'))
    ).all()
    if not docs:
        return f"<p>No doctors found matching <strong>{query_text}</strong>.</p>"
    rows = ""
    for d in docs:
        total_apts = Appointment.query.filter_by(doctor_id=d.id).count()
        rows += f"""<div class="bot-record-card">
          <div class="d-flex align-items-center gap-2 mb-1">
            <span class="avatar-init">{d.full_name[0]}</span>
            <div><div class="fw-bold">{d.full_name}</div>
            <div class="small text-muted">{d.specialization or '—'} · {d.department.name if d.department else '—'}</div></div>
          </div>
          <div class="bot-vitals">
            <span>📞 {d.phone or '—'}</span>
            <span>📋 {total_apts} appointments</span>
            <span class="badge bg-{'success' if d.status=='active' else 'secondary'}">{d.status}</span>
          </div>
        </div>"""
    return f'<div class="fw-bold mb-2">Found {len(docs)} doctor(s):</div>' + rows


HELP_MSG = """
<div class="bot-card">
  <div class="bot-card-header"><span style="font-size:1.4rem">🤖</span>
    <div><div class="fw-bold">HMS AI Assistant</div><div class="small text-muted">What can I help you with?</div></div>
  </div>
  <div class="bot-card-body">
    <div class="fw-semibold mb-2">Ask me about patients:</div>
    <div class="bot-quick-list">
      <span>Show patient John Smith</span>
      <span>P123456 ka data</span>
      <span>Bob ka appointments</span>
      <span>Alice ki bills</span>
      <span>Xavier ka lab results</span>
      <span>Frank ki medical records</span>
    </div>
    <div class="fw-semibold mb-2 mt-3">Hospital stats:</div>
    <div class="bot-quick-list">
      <span>Aaj ka stats</span>
      <span>Today's appointments</span>
      <span>Hospital overview</span>
      <span>Kitne patients hain</span>
    </div>
    <div class="fw-semibold mb-2 mt-3">Doctors:</div>
    <div class="bot-quick-list">
      <span>Dr. Jennifer Miller</span>
      <span>Cardiology doctor</span>
      <span>Available doctors</span>
    </div>
  </div>
</div>"""


def _process_message(msg):
    """Main intent engine — returns (html_response, quick_replies)."""
    m = msg.lower().strip()

    # ── Help ────────────────────────────────────────────────────────────────
    if any(w in m for w in ['help', 'kya kar', 'kya ho', 'guide', 'commands', 'what can']):
        return HELP_MSG, ['Today stats', 'Hospital overview', 'Show all doctors']

    # ── Today stats ─────────────────────────────────────────────────────────
    if any(w in m for w in ['aaj', 'today', 'aaj ka', "today's stats", 'abhi', 'kitna chal']):
        return _today_stats(), ['Hospital overview', 'Pending labs', 'Admitted patients']

    # ── Hospital overview ───────────────────────────────────────────────────
    if any(w in m for w in ['hospital', 'overview', 'total patients', 'kitne patients', 'stats', 'summary']):
        return _hospital_stats(), ["Today's appointments", 'Show all doctors']

    # ── Pending labs ────────────────────────────────────────────────────────
    if any(w in m for w in ['pending lab', 'lab pending', 'pending test', 'test pending']):
        tests = LabTest.query.filter_by(status='pending').order_by(LabTest.test_date.desc()).limit(10).all()
        if not tests:
            return "<p>✅ No pending lab tests!</p>", []
        rows = ''.join(f"<tr><td>{t.medical_record.patient.full_name}</td><td>{t.test_name}</td><td>{t.test_date.strftime('%d %b') if t.test_date else '—'}</td></tr>" for t in tests)
        return f"""<div class="bot-card"><div class="bot-card-header"><span>🧪</span><div><div class="fw-bold">Pending Lab Tests ({len(tests)})</div></div></div>
<div class="bot-table-wrap"><table class="bot-table"><thead><tr><th>Patient</th><th>Test</th><th>Date</th></tr></thead><tbody>{rows}</tbody></table></div></div>""", []

    # ── Admitted patients ───────────────────────────────────────────────────
    if any(w in m for w in ['admitted', 'inpatient', 'ward me', 'bharte']):
        adms = Admission.query.filter_by(status='admitted').order_by(Admission.admission_date.desc()).all()
        if not adms:
            return "<p>No patients currently admitted.</p>", []
        rows = ''.join(f"<tr><td>{a.patient.full_name}</td><td>{a.bed.bed_number if a.bed else '—'}</td><td>{a.admitting_doctor.full_name if a.admitting_doctor else '—'}</td><td>{a.admission_date.strftime('%d %b')}</td></tr>" for a in adms)
        return f"""<div class="bot-card"><div class="bot-card-header"><span>🛏️</span><div><div class="fw-bold">Currently Admitted ({len(adms)})</div></div></div>
<div class="bot-table-wrap"><table class="bot-table"><thead><tr><th>Patient</th><th>Bed</th><th>Doctor</th><th>Admitted</th></tr></thead><tbody>{rows}</tbody></table></div></div>""", []

    # ── Doctor queries ───────────────────────────────────────────────────────
    if any(w in m for w in ['doctor', 'dr.', 'dr ', 'physician', 'specialist', 'cardio', 'ortho', 'gynec', 'neuro', 'pediatr', 'derma', 'surgeon']):
        # Extract search term - remove intent words
        search = m.replace('doctor', '').replace('dr.', '').replace('dr ', '').replace('show', '').replace('find', '').strip()
        if not search:
            search = msg  # use original if nothing left
        return _doctor_info(search.strip()), ['Today stats', 'Hospital overview']

    # ── Patient-specific queries ─────────────────────────────────────────────
    # Determine intent (what do they want about the patient)
    wants_appointments = any(w in m for w in ['appointment', 'schedule', 'booking', 'visit', 'appoint', 'milna'])
    wants_bills = any(w in m for w in ['bill', 'billing', 'payment', 'invoice', 'outstanding', 'baaki', 'paisa', 'amount'])
    wants_labs = any(w in m for w in ['lab', 'test', 'result', 'report', 'blood test', 'khaoon', 'nateeja'])
    wants_records = any(w in m for w in ['record', 'history', 'diagnosis', 'treatment', 'medical', 'prescription', 'report', 'taareekh'])

    # Strip intent keywords to get patient name/ID
    strip_words = ['show', 'tell me about', 'batao', 'dikhao', 'patient', 'ka data', 'ki info',
                   'appointment', 'bill', 'lab', 'medical record', 'history', 'result',
                   'ka', 'ki', 'ke', 'ko', 'kya', 'hai', 'the', 'a', 'an', 'for', 'of', 'about']
    search_term = m
    for w in strip_words:
        search_term = search_term.replace(w, ' ')
    search_term = ' '.join(search_term.split()).strip()

    # Try to find patients
    patients_found = []
    if search_term and len(search_term) >= 2:
        patients_found = _find_patients(search_term)
    if not patients_found and len(msg.strip()) >= 2:
        # Try full original message
        patients_found = _find_patients(msg.strip())

    if patients_found:
        if len(patients_found) > 1:
            # Multiple matches — show list
            options = ''.join(
                f'<div class="bot-match-item" onclick="setMsg(\'{p.full_name}\')">'
                f'<span class="avatar-init small">{p.full_name[0]}</span>'
                f'<span><strong>{p.full_name}</strong> · {p.patient_id} · Age {p.age}</span></div>'
                for p in patients_found[:6]
            )
            return f'<div class="fw-semibold mb-2">Found {len(patients_found)} matching patients — click to select:</div>{options}', []

        p = patients_found[0]
        # Single patient — respond based on intent
        if wants_appointments:
            return _patient_appointments(p), [f'{p.full_name} ka bill', f'{p.full_name} ki labs', f'{p.full_name} ka profile']
        elif wants_bills:
            return _patient_bills(p), [f'{p.full_name} ka appointment', f'{p.full_name} ki labs']
        elif wants_labs:
            return _patient_labs(p), [f'{p.full_name} ka appointment', f'{p.full_name} ka bill']
        elif wants_records:
            return _patient_records(p), [f'{p.full_name} ka appointment', f'{p.full_name} ka bill', f'{p.full_name} ki labs']
        else:
            # Default: full profile card
            return _patient_card(p), [
                f'{p.full_name} ka appointment',
                f'{p.full_name} ka bill',
                f'{p.full_name} ki labs',
                f'{p.full_name} ki records',
            ]

    # ── Nothing matched ──────────────────────────────────────────────────────
    return f"""<div class="bot-not-found">
  <div>🤔</div>
  <div>Mujhe samajh nahi aya: <strong>"{msg[:60]}"</strong></div>
  <div class="small text-muted mt-1">Patient name/ID, ya "help" type karen</div>
</div>""", ['help', 'Today stats', 'Hospital overview']


@ai_bp.route('/chat', methods=['GET'])
@login_required
def chat():
    # Pre-load recent patients for quick access
    recent = Patient.query.order_by(Patient.created_at.desc()).limit(8).all()
    return render_template('ai/chat.html', recent_patients=recent)


@ai_bp.route('/chat/message', methods=['POST'])
@login_required
def chat_message():
    data = request.get_json(force=True) or {}
    msg = (data.get('message') or '').strip()
    if not msg:
        return jsonify({'html': '<p class="text-muted">Kuch type karen…</p>', 'quick': []})
    html, quick = _process_message(msg)
    return jsonify({'html': html, 'quick': quick})
