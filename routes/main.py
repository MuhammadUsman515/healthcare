from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import (db, Patient, Doctor, Appointment, Bill, Admission, Medicine,
                    Department, Staff, BloodInventory, Ambulance, OPDQueue,
                    BloodRequest, AmbulanceDispatch, Referral)
from datetime import datetime, date, timedelta
from sqlalchemy import func

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    today = date.today()
    org_id = current_user.org_id

    def tf(query, model):
        """Apply tenant filter if user has an org."""
        return query.filter(model.org_id == org_id) if org_id else query

    # Core stats
    total_patients = tf(Patient.query.filter_by(status='active'), Patient).count()
    total_doctors = tf(Doctor.query.filter_by(status='active'), Doctor).count()
    today_appointments = tf(Appointment.query.filter_by(appointment_date=today), Appointment).count()
    admitted_patients = tf(Admission.query.filter_by(status='admitted'), Admission).count()

    # Revenue this month
    first_day = today.replace(day=1)
    monthly_revenue = tf(
        db.session.query(func.sum(Bill.paid_amount)).filter(Bill.bill_date >= first_day),
        Bill
    ).scalar() or 0

    # Outstanding amount
    outstanding = tf(
        db.session.query(func.sum(Bill.total_amount - Bill.paid_amount)).filter(
            Bill.payment_status.in_(['pending', 'partial'])
        ), Bill
    ).scalar() or 0

    # Pending bills
    pending_bills = tf(Bill.query.filter_by(payment_status='pending'), Bill).count()

    # Today's appointments
    appointments_today = tf(
        Appointment.query.filter_by(appointment_date=today), Appointment
    ).order_by(Appointment.appointment_time).limit(10).all()

    # Recent patients
    recent_patients = tf(Patient.query, Patient).order_by(Patient.created_at.desc()).limit(5).all()

    # Low stock medicines
    low_stock = tf(Medicine.query.filter(
        Medicine.stock_quantity <= Medicine.reorder_level
    ), Medicine).count()

    # Staff count
    total_staff = tf(Staff.query.filter_by(status='active'), Staff).count()

    # OPD waiting today
    opd_waiting = tf(OPDQueue.query.filter_by(queue_date=today, status='waiting'), OPDQueue).count()

    # Ambulances available
    ambulances_available = tf(Ambulance.query.filter_by(status='available'), Ambulance).count()
    ambulances_total = tf(Ambulance.query, Ambulance).count()

    # Blood bank - critical stock
    critical_blood = tf(
        BloodInventory.query.filter(BloodInventory.units_available < 5), BloodInventory
    ).count()

    # Pending blood requests
    pending_blood = tf(BloodRequest.query.filter_by(status='pending'), BloodRequest).count()

    # Active dispatches
    active_dispatches = tf(AmbulanceDispatch.query.filter_by(status='dispatched'), AmbulanceDispatch).count()

    # Pending referrals
    pending_referrals = tf(Referral.query.filter_by(status='pending'), Referral).count()

    # Appointment stats for chart (last 7 days)
    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        count = tf(Appointment.query.filter_by(appointment_date=day), Appointment).count()
        chart_labels.append(day.strftime('%a'))
        chart_data.append(count)

    # Department stats
    dept_q = Department.query
    if org_id:
        dept_q = dept_q.filter_by(org_id=org_id)
    departments = dept_q.all()
    dept_stats = []
    for dept in departments:
        doc_count = Doctor.query.filter_by(department_id=dept.id, status='active').count()
        dept_stats.append({'name': dept.name, 'doctors': doc_count})

    return render_template('dashboard.html',
        today=today,
        total_patients=total_patients,
        total_doctors=total_doctors,
        today_appointments=today_appointments,
        admitted_patients=admitted_patients,
        monthly_revenue=monthly_revenue,
        outstanding=outstanding,
        pending_bills=pending_bills,
        appointments_today=appointments_today,
        recent_patients=recent_patients,
        low_stock=low_stock,
        total_staff=total_staff,
        opd_waiting=opd_waiting,
        ambulances_available=ambulances_available,
        ambulances_total=ambulances_total,
        critical_blood=critical_blood,
        pending_blood=pending_blood,
        active_dispatches=active_dispatches,
        pending_referrals=pending_referrals,
        chart_labels=chart_labels,
        chart_data=chart_data,
        dept_stats=dept_stats,
    )
