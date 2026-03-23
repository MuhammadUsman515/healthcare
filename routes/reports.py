from flask import Blueprint, render_template, request
from flask_login import login_required
from models import (db, Patient, Doctor, Appointment, Bill, Medicine, Admission,
                    MedicalRecord, LabTest, Ward, Bed, BloodInventory, BloodRequest,
                    Staff, Department, Prescription, OPDQueue)
from datetime import datetime, date, timedelta
from sqlalchemy import func, extract, case

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


def get_date_range(period):
    today = date.today()
    if period == 'week':
        return today - timedelta(days=7), today
    elif period == 'year':
        return today.replace(month=1, day=1), today
    else:  # month default
        return today.replace(day=1), today


@reports_bp.route('/')
@login_required
def index():
    # Quick stats for the index page
    today = date.today()
    month_start = today.replace(day=1)

    stats = {
        'total_patients': Patient.query.count(),
        'new_this_month': Patient.query.filter(Patient.created_at >= month_start).count(),
        'appointments_this_month': Appointment.query.filter(Appointment.appointment_date >= month_start).count(),
        'revenue_this_month': db.session.query(func.sum(Bill.total_amount)).filter(Bill.bill_date >= month_start).scalar() or 0,
        'outstanding': (db.session.query(func.sum(Bill.total_amount)).filter(Bill.bill_date >= month_start).scalar() or 0) -
                       (db.session.query(func.sum(Bill.paid_amount)).filter(Bill.bill_date >= month_start).scalar() or 0),
        'completion_rate': 0,
    }
    total_appts = stats['appointments_this_month']
    if total_appts > 0:
        completed = Appointment.query.filter(
            Appointment.appointment_date >= month_start,
            Appointment.status == 'completed'
        ).count()
        stats['completion_rate'] = round(completed / total_appts * 100, 1)

    return render_template('reports/index.html', stats=stats)


@reports_bp.route('/patients')
@login_required
def patient_report():
    period = request.args.get('period', 'month')
    start, today = get_date_range(period)

    new_patients = Patient.query.filter(Patient.created_at >= start).count()
    total_patients = Patient.query.count()
    active_patients = Patient.query.filter_by(status='active').count()
    inactive_patients = total_patients - active_patients

    gender_stats = db.session.query(Patient.gender, func.count(Patient.id)).group_by(Patient.gender).all()
    blood_stats = db.session.query(Patient.blood_group, func.count(Patient.id)).group_by(Patient.blood_group).order_by(func.count(Patient.id).desc()).all()

    # Age group distribution
    all_patients = Patient.query.all()
    age_groups = {'0-17': 0, '18-35': 0, '36-50': 0, '51-65': 0, '65+': 0}
    total_age = 0
    age_count = 0
    for p in all_patients:
        try:
            a = p.age
            total_age += a
            age_count += 1
            if a <= 17: age_groups['0-17'] += 1
            elif a <= 35: age_groups['18-35'] += 1
            elif a <= 50: age_groups['36-50'] += 1
            elif a <= 65: age_groups['51-65'] += 1
            else: age_groups['65+'] += 1
        except Exception:
            pass
    avg_age = round(total_age / age_count, 1) if age_count else 0

    # Top chronic conditions
    conditions_raw = db.session.query(Patient.chronic_conditions).filter(
        Patient.chronic_conditions.isnot(None),
        Patient.chronic_conditions != ''
    ).all()
    condition_counts = {}
    for (c,) in conditions_raw:
        for term in c.split(','):
            t = term.strip().lower()
            if t:
                condition_counts[t] = condition_counts.get(t, 0) + 1
    top_conditions = sorted(condition_counts.items(), key=lambda x: x[1], reverse=True)[:8]

    # Recent registrations
    recent_patients = Patient.query.filter(
        Patient.created_at >= start
    ).order_by(Patient.created_at.desc()).limit(15).all()

    # Daily registrations for trend (last 14 days)
    daily_reg = []
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        cnt = Patient.query.filter(
            func.date(Patient.created_at) == day
        ).count()
        daily_reg.append({'date': day.strftime('%d %b'), 'count': cnt})

    return render_template('reports/patients.html',
        period=period, start=start, today=today,
        new_patients=new_patients, total_patients=total_patients,
        active_patients=active_patients, inactive_patients=inactive_patients,
        avg_age=avg_age,
        gender_stats=gender_stats, blood_stats=blood_stats,
        age_groups=age_groups, top_conditions=top_conditions,
        recent_patients=recent_patients, daily_reg=daily_reg,
    )


@reports_bp.route('/appointments')
@login_required
def appointment_report():
    period = request.args.get('period', 'month')
    start, today = get_date_range(period)

    total = Appointment.query.filter(Appointment.appointment_date >= start).count()
    completed = Appointment.query.filter(Appointment.appointment_date >= start, Appointment.status == 'completed').count()
    cancelled = Appointment.query.filter(Appointment.appointment_date >= start, Appointment.status == 'cancelled').count()
    scheduled = Appointment.query.filter(Appointment.appointment_date >= start, Appointment.status == 'scheduled').count()
    no_show = Appointment.query.filter(Appointment.appointment_date >= start, Appointment.status == 'no-show').count()
    completion_rate = round(completed / total * 100, 1) if total > 0 else 0
    cancellation_rate = round(cancelled / total * 100, 1) if total > 0 else 0

    # By doctor
    doctor_stats = db.session.query(
        Doctor.first_name, Doctor.last_name, Doctor.specialization,
        func.count(Appointment.id).label('total'),
        func.sum(func.case((Appointment.status == 'completed', 1), else_=0)).label('done'),
    ).join(Appointment, Doctor.id == Appointment.doctor_id).filter(
        Appointment.appointment_date >= start
    ).group_by(Doctor.id).order_by(func.count(Appointment.id).desc()).limit(10).all()

    # Daily trend (last 14 days or period days)
    days = 14 if period == 'month' else (7 if period == 'week' else 30)
    daily_trend = []
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        cnt = Appointment.query.filter(func.date(Appointment.appointment_date) == day).count()
        daily_trend.append({'date': day.strftime('%d %b'), 'count': cnt})

    # Recent appointments
    recent_appts = Appointment.query.filter(
        Appointment.appointment_date >= start
    ).order_by(Appointment.appointment_date.desc()).limit(20).all()

    # Top reasons/complaints
    reasons = db.session.query(Appointment.reason, func.count(Appointment.id)).filter(
        Appointment.appointment_date >= start,
        Appointment.reason.isnot(None),
        Appointment.reason != ''
    ).group_by(Appointment.reason).order_by(func.count(Appointment.id).desc()).limit(8).all()

    return render_template('reports/appointments.html',
        period=period, start=start, today=today,
        total=total, completed=completed, cancelled=cancelled,
        scheduled=scheduled, no_show=no_show,
        completion_rate=completion_rate, cancellation_rate=cancellation_rate,
        doctor_stats=doctor_stats, daily_trend=daily_trend,
        recent_appts=recent_appts, reasons=reasons,
    )


@reports_bp.route('/revenue')
@login_required
def revenue_report():
    period = request.args.get('period', 'month')
    start, today = get_date_range(period)

    total_billed = db.session.query(func.sum(Bill.total_amount)).filter(Bill.bill_date >= start).scalar() or 0
    total_collected = db.session.query(func.sum(Bill.paid_amount)).filter(Bill.bill_date >= start).scalar() or 0
    outstanding = total_billed - total_collected
    total_bills = Bill.query.filter(Bill.bill_date >= start).count()
    avg_bill = round(total_billed / total_bills, 2) if total_bills else 0
    collection_rate = round(total_collected / total_billed * 100, 1) if total_billed > 0 else 0

    status_stats = db.session.query(
        Bill.payment_status, func.count(Bill.id), func.sum(Bill.total_amount)
    ).filter(Bill.bill_date >= start).group_by(Bill.payment_status).all()

    # Daily revenue trend
    days = 14 if period == 'month' else (7 if period == 'week' else 30)
    daily_revenue = []
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        amt = db.session.query(func.sum(Bill.paid_amount)).filter(
            func.date(Bill.bill_date) == day
        ).scalar() or 0
        daily_revenue.append({'date': day.strftime('%d %b'), 'amount': float(amt)})

    # Recent bills
    recent_bills = Bill.query.filter(
        Bill.bill_date >= start
    ).order_by(Bill.bill_date.desc()).limit(20).all()

    # Top paying patients
    top_patients = db.session.query(
        Patient.first_name, Patient.last_name, Patient.patient_id,
        func.sum(Bill.paid_amount).label('paid'),
        func.count(Bill.id).label('bills')
    ).join(Bill, Patient.id == Bill.patient_id).filter(
        Bill.bill_date >= start
    ).group_by(Patient.id).order_by(func.sum(Bill.paid_amount).desc()).limit(8).all()

    return render_template('reports/revenue.html',
        period=period, start=start, today=today,
        total_billed=total_billed, total_collected=total_collected,
        outstanding=outstanding, total_bills=total_bills,
        avg_bill=avg_bill, collection_rate=collection_rate,
        status_stats=status_stats, daily_revenue=daily_revenue,
        recent_bills=recent_bills, top_patients=top_patients,
    )


# ─── DOCTOR PERFORMANCE REPORT ────────────────────────────────────────────────
@reports_bp.route('/doctors')
@login_required
def doctor_report():
    period = request.args.get('period', 'month')
    start, today = get_date_range(period)

    total_doctors = Doctor.query.count()
    active_doctors = Doctor.query.filter_by(status='active').count()

    # Per-doctor stats
    doctor_stats = db.session.query(
        Doctor,
        func.count(Appointment.id).label('total_appts'),
        func.sum(case((Appointment.status == 'completed', 1), else_=0)).label('completed'),
        func.sum(case((Appointment.status == 'cancelled', 1), else_=0)).label('cancelled'),
    ).outerjoin(Appointment, (Doctor.id == Appointment.doctor_id) & (Appointment.appointment_date >= start)
    ).group_by(Doctor.id).order_by(func.count(Appointment.id).desc()).all()

    # Revenue per doctor (via billing items is complex - approximate via appointments)
    # Specialization breakdown
    spec_stats = db.session.query(
        Doctor.specialization, func.count(Doctor.id)
    ).group_by(Doctor.specialization).order_by(func.count(Doctor.id).desc()).all()

    # Department breakdown
    dept_stats = db.session.query(
        Department.name, func.count(Doctor.id)
    ).outerjoin(Doctor, Doctor.department_id == Department.id
    ).group_by(Department.id).order_by(func.count(Doctor.id).desc()).all()

    return render_template('reports/doctors.html',
        period=period, start=start, today=today,
        total_doctors=total_doctors, active_doctors=active_doctors,
        doctor_stats=doctor_stats, spec_stats=spec_stats, dept_stats=dept_stats,
    )


# ─── LAB REPORT ───────────────────────────────────────────────────────────────
@reports_bp.route('/lab')
@login_required
def lab_report():
    period = request.args.get('period', 'month')
    start, today = get_date_range(period)

    total = LabTest.query.filter(LabTest.test_date >= start).count()
    pending = LabTest.query.filter(LabTest.test_date >= start, LabTest.status == 'pending').count()
    completed = LabTest.query.filter(LabTest.test_date >= start, LabTest.status == 'completed').count()
    cancelled = LabTest.query.filter(LabTest.test_date >= start, LabTest.status == 'cancelled').count()
    completion_rate = round(completed / total * 100, 1) if total > 0 else 0

    # Top tests
    top_tests = db.session.query(
        LabTest.test_name, func.count(LabTest.id).label('cnt')
    ).filter(LabTest.test_date >= start
    ).group_by(LabTest.test_name).order_by(func.count(LabTest.id).desc()).limit(10).all()

    # Daily trend
    daily = []
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        cnt = LabTest.query.filter(func.date(LabTest.test_date) == day).count()
        daily.append({'date': day.strftime('%d %b'), 'count': cnt})

    # Recent tests with patient info
    recent = db.session.query(LabTest, Patient).join(
        MedicalRecord, LabTest.medical_record_id == MedicalRecord.id
    ).join(Patient, MedicalRecord.patient_id == Patient.id
    ).filter(LabTest.test_date >= start
    ).order_by(LabTest.test_date.desc()).limit(20).all()

    return render_template('reports/lab.html',
        period=period, start=start, today=today,
        total=total, pending=pending, completed=completed,
        cancelled=cancelled, completion_rate=completion_rate,
        top_tests=top_tests, daily=daily, recent=recent,
    )


# ─── PHARMACY / STOCK REPORT ──────────────────────────────────────────────────
@reports_bp.route('/pharmacy')
@login_required
def pharmacy_report():
    all_medicines = Medicine.query.all()
    total = len(all_medicines)
    low_stock = [m for m in all_medicines if m.is_low_stock]
    out_of_stock = [m for m in all_medicines if m.stock_quantity == 0]

    today_d = date.today()
    expiring_soon = [m for m in all_medicines
                     if m.expiry_date and (m.expiry_date - today_d).days <= 90 and m.expiry_date >= today_d]
    expired = [m for m in all_medicines
               if m.expiry_date and m.expiry_date < today_d]

    # Category breakdown
    cat_stats = db.session.query(
        Medicine.category, func.count(Medicine.id), func.sum(Medicine.stock_quantity)
    ).group_by(Medicine.category).order_by(func.count(Medicine.id).desc()).all()

    # Total inventory value
    total_value = sum((m.stock_quantity * m.unit_price) for m in all_medicines)

    # Top medicines by stock value
    top_by_value = sorted(all_medicines, key=lambda m: m.stock_quantity * m.unit_price, reverse=True)[:10]

    return render_template('reports/pharmacy.html',
        total=total, low_stock=low_stock, out_of_stock=out_of_stock,
        expiring_soon=expiring_soon, expired=expired,
        cat_stats=cat_stats, total_value=total_value,
        top_by_value=top_by_value, all_medicines=all_medicines,
    )


# ─── WARD & ADMISSIONS REPORT ─────────────────────────────────────────────────
@reports_bp.route('/wards')
@login_required
def ward_report():
    period = request.args.get('period', 'month')
    start, today = get_date_range(period)

    wards = Ward.query.all()
    all_beds = Bed.query.all()
    total_beds = len(all_beds)
    occupied_beds = sum(1 for b in all_beds if b.status == 'occupied')
    available_beds = sum(1 for b in all_beds if b.status == 'available')
    maintenance_beds = sum(1 for b in all_beds if b.status == 'maintenance')
    occupancy_rate = round(occupied_beds / total_beds * 100, 1) if total_beds else 0

    total_admissions = Admission.query.filter(Admission.admission_date >= start).count()
    current_admissions = Admission.query.filter_by(status='admitted').count()
    discharged = Admission.query.filter(
        Admission.admission_date >= start, Admission.status == 'discharged'
    ).count()

    # Avg length of stay
    discharged_list = Admission.query.filter(
        Admission.admission_date >= start,
        Admission.status == 'discharged',
        Admission.discharge_date.isnot(None)
    ).all()
    avg_los = 0
    if discharged_list:
        total_days = sum((a.discharge_date - a.admission_date).days for a in discharged_list)
        avg_los = round(total_days / len(discharged_list), 1)

    # Ward-wise stats
    ward_stats = []
    for w in wards:
        beds = w.beds
        occ = sum(1 for b in beds if b.status == 'occupied')
        total_w = len(beds)
        ward_stats.append({
            'ward': w,
            'total': total_w,
            'occupied': occ,
            'available': sum(1 for b in beds if b.status == 'available'),
            'rate': round(occ / total_w * 100, 1) if total_w else 0,
        })

    # Recent admissions
    recent_admissions = Admission.query.filter(
        Admission.admission_date >= start
    ).order_by(Admission.admission_date.desc()).limit(20).all()

    return render_template('reports/wards.html',
        period=period, start=start, today=today,
        total_beds=total_beds, occupied_beds=occupied_beds,
        available_beds=available_beds, maintenance_beds=maintenance_beds,
        occupancy_rate=occupancy_rate,
        total_admissions=total_admissions, current_admissions=current_admissions,
        discharged=discharged, avg_los=avg_los,
        ward_stats=ward_stats, recent_admissions=recent_admissions,
    )


# ─── BLOOD BANK REPORT ────────────────────────────────────────────────────────
@reports_bp.route('/blood-bank')
@login_required
def blood_bank_report():
    period = request.args.get('period', 'month')
    start, today = get_date_range(period)

    inventory = BloodInventory.query.order_by(BloodInventory.blood_group).all()
    total_units = sum(i.units_available for i in inventory)
    critical = [i for i in inventory if i.units_available < 5]

    total_requests = BloodRequest.query.filter(BloodRequest.request_date >= start).count()
    approved = BloodRequest.query.filter(BloodRequest.request_date >= start, BloodRequest.status == 'approved').count()
    pending = BloodRequest.query.filter(BloodRequest.request_date >= start, BloodRequest.status == 'pending').count()
    issued = BloodRequest.query.filter(BloodRequest.request_date >= start, BloodRequest.status == 'issued').count()
    cancelled_req = BloodRequest.query.filter(BloodRequest.request_date >= start, BloodRequest.status == 'cancelled').count()
    fulfillment_rate = round(issued / total_requests * 100, 1) if total_requests > 0 else 0

    # By blood group demand
    demand_stats = db.session.query(
        BloodRequest.blood_group,
        func.count(BloodRequest.id).label('requests'),
        func.sum(BloodRequest.units_required).label('units_req'),
        func.sum(BloodRequest.units_issued).label('units_issued'),
    ).filter(BloodRequest.request_date >= start
    ).group_by(BloodRequest.blood_group).order_by(func.count(BloodRequest.id).desc()).all()

    recent_requests = BloodRequest.query.filter(
        BloodRequest.request_date >= start
    ).order_by(BloodRequest.request_date.desc()).limit(20).all()

    return render_template('reports/blood_bank.html',
        period=period, start=start, today=today,
        inventory=inventory, total_units=total_units, critical=critical,
        total_requests=total_requests, approved=approved, pending=pending,
        issued=issued, cancelled_req=cancelled_req,
        fulfillment_rate=fulfillment_rate,
        demand_stats=demand_stats, recent_requests=recent_requests,
    )
