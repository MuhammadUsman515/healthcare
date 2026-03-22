from flask import Blueprint, render_template
from flask_login import login_required
from models import db, Patient, Doctor, Appointment, Bill, Admission, Medicine, Department
from datetime import datetime, date, timedelta
from sqlalchemy import func

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    today = date.today()

    # Summary stats
    total_patients = Patient.query.filter_by(status='active').count()
    total_doctors = Doctor.query.filter_by(status='active').count()
    today_appointments = Appointment.query.filter_by(appointment_date=today).count()
    admitted_patients = Admission.query.filter_by(status='admitted').count()

    # Revenue this month
    first_day = today.replace(day=1)
    monthly_revenue = db.session.query(func.sum(Bill.paid_amount)).filter(
        Bill.bill_date >= first_day
    ).scalar() or 0

    # Pending bills
    pending_bills = Bill.query.filter_by(payment_status='pending').count()

    # Today's appointments
    appointments_today = Appointment.query.filter_by(
        appointment_date=today
    ).order_by(Appointment.appointment_time).limit(10).all()

    # Recent patients
    recent_patients = Patient.query.order_by(Patient.created_at.desc()).limit(5).all()

    # Low stock medicines
    low_stock = Medicine.query.filter(
        Medicine.stock_quantity <= Medicine.reorder_level
    ).count()

    # Appointment stats for chart (last 7 days)
    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        count = Appointment.query.filter_by(appointment_date=day).count()
        chart_labels.append(day.strftime('%a'))
        chart_data.append(count)

    # Department stats
    departments = Department.query.all()
    dept_stats = []
    for dept in departments:
        doc_count = Doctor.query.filter_by(department_id=dept.id, status='active').count()
        dept_stats.append({'name': dept.name, 'doctors': doc_count})

    return render_template('dashboard.html',
        total_patients=total_patients,
        total_doctors=total_doctors,
        today_appointments=today_appointments,
        admitted_patients=admitted_patients,
        monthly_revenue=monthly_revenue,
        pending_bills=pending_bills,
        appointments_today=appointments_today,
        recent_patients=recent_patients,
        low_stock=low_stock,
        chart_labels=chart_labels,
        chart_data=chart_data,
        dept_stats=dept_stats,
        today=today
    )
