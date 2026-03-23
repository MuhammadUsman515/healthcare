from flask import Blueprint, render_template, request
from flask_login import login_required
from models import db, Patient, Doctor, Appointment, Bill, Medicine, Admission, MedicalRecord
from datetime import datetime, date, timedelta
from sqlalchemy import func, extract

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
