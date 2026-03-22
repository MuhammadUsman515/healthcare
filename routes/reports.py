from flask import Blueprint, render_template, request
from flask_login import login_required
from models import db, Patient, Doctor, Appointment, Bill, Medicine, Admission
from datetime import datetime, date, timedelta
from sqlalchemy import func

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


@reports_bp.route('/')
@login_required
def index():
    return render_template('reports/index.html')


@reports_bp.route('/patients')
@login_required
def patient_report():
    period = request.args.get('period', 'month')
    today = date.today()

    if period == 'week':
        start = today - timedelta(days=7)
    elif period == 'month':
        start = today.replace(day=1)
    elif period == 'year':
        start = today.replace(month=1, day=1)
    else:
        start = today.replace(day=1)

    new_patients = Patient.query.filter(Patient.created_at >= start).count()
    total_patients = Patient.query.count()
    active_patients = Patient.query.filter_by(status='active').count()

    gender_stats = db.session.query(Patient.gender, func.count(Patient.id)).group_by(Patient.gender).all()
    blood_stats = db.session.query(Patient.blood_group, func.count(Patient.id)).group_by(Patient.blood_group).all()

    return render_template('reports/patients.html',
        period=period,
        new_patients=new_patients,
        total_patients=total_patients,
        active_patients=active_patients,
        gender_stats=gender_stats,
        blood_stats=blood_stats
    )


@reports_bp.route('/appointments')
@login_required
def appointment_report():
    period = request.args.get('period', 'month')
    today = date.today()

    if period == 'week':
        start = today - timedelta(days=7)
    elif period == 'month':
        start = today.replace(day=1)
    elif period == 'year':
        start = today.replace(month=1, day=1)
    else:
        start = today.replace(day=1)

    total = Appointment.query.filter(Appointment.appointment_date >= start).count()
    completed = Appointment.query.filter(Appointment.appointment_date >= start, Appointment.status == 'completed').count()
    cancelled = Appointment.query.filter(Appointment.appointment_date >= start, Appointment.status == 'cancelled').count()
    scheduled = Appointment.query.filter(Appointment.appointment_date >= start, Appointment.status == 'scheduled').count()

    # By doctor
    doctor_stats = db.session.query(
        Doctor.first_name, Doctor.last_name, func.count(Appointment.id)
    ).join(Appointment, Doctor.id == Appointment.doctor_id).filter(
        Appointment.appointment_date >= start
    ).group_by(Doctor.id).order_by(func.count(Appointment.id).desc()).limit(10).all()

    return render_template('reports/appointments.html',
        period=period,
        total=total,
        completed=completed,
        cancelled=cancelled,
        scheduled=scheduled,
        doctor_stats=doctor_stats
    )


@reports_bp.route('/revenue')
@login_required
def revenue_report():
    period = request.args.get('period', 'month')
    today = date.today()

    if period == 'week':
        start = today - timedelta(days=7)
    elif period == 'month':
        start = today.replace(day=1)
    elif period == 'year':
        start = today.replace(month=1, day=1)
    else:
        start = today.replace(day=1)

    total_billed = db.session.query(func.sum(Bill.total_amount)).filter(Bill.bill_date >= start).scalar() or 0
    total_collected = db.session.query(func.sum(Bill.paid_amount)).filter(Bill.bill_date >= start).scalar() or 0
    outstanding = total_billed - total_collected

    status_stats = db.session.query(Bill.payment_status, func.count(Bill.id), func.sum(Bill.total_amount)).filter(
        Bill.bill_date >= start
    ).group_by(Bill.payment_status).all()

    return render_template('reports/revenue.html',
        period=period,
        total_billed=total_billed,
        total_collected=total_collected,
        outstanding=outstanding,
        status_stats=status_stats
    )
