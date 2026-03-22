from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from models import db, Doctor, Department, User, Appointment
from datetime import datetime, date
from werkzeug.security import generate_password_hash

doctors_bp = Blueprint('doctors', __name__, url_prefix='/doctors')


@doctors_bp.route('/')
@login_required
def index():
    search = request.args.get('search', '')
    dept_id = request.args.get('department', '')

    query = Doctor.query
    if search:
        query = query.filter(
            (Doctor.first_name.ilike(f'%{search}%')) |
            (Doctor.last_name.ilike(f'%{search}%')) |
            (Doctor.specialization.ilike(f'%{search}%'))
        )
    if dept_id:
        query = query.filter_by(department_id=int(dept_id))

    doctors = query.filter_by(status='active').order_by(Doctor.first_name).all()
    departments = Department.query.all()
    return render_template('doctors/index.html', doctors=doctors, departments=departments,
                           search=search, dept_id=dept_id)


@doctors_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    departments = Department.query.all()

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password') or 'Doctor@123'

        user = User(username=username, email=email, role='doctor')
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        dept_id = request.form.get('department_id')
        doctor = Doctor(
            user_id=user.id,
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            specialization=request.form.get('specialization'),
            department_id=int(dept_id) if dept_id else None,
            phone=request.form.get('phone'),
            email=email,
            license_number=request.form.get('license_number'),
            qualification=request.form.get('qualification'),
            experience_years=int(request.form.get('experience_years') or 0),
            consultation_fee=float(request.form.get('consultation_fee') or 0),
            available_days=request.form.get('available_days', 'Mon,Tue,Wed,Thu,Fri'),
            available_from=request.form.get('available_from', '09:00'),
            available_to=request.form.get('available_to', '17:00'),
        )
        db.session.add(doctor)
        db.session.commit()
        flash(f'Dr. {doctor.first_name} {doctor.last_name} added successfully!', 'success')
        return redirect(url_for('doctors.view', id=doctor.id))

    return render_template('doctors/new.html', departments=departments)


@doctors_bp.route('/<int:id>')
@login_required
def view(id):
    doctor = Doctor.query.get_or_404(id)
    today = date.today()
    upcoming = Appointment.query.filter_by(
        doctor_id=id, status='scheduled'
    ).filter(Appointment.appointment_date >= today).order_by(Appointment.appointment_date).limit(10).all()

    total_patients = Appointment.query.filter_by(doctor_id=id).distinct(Appointment.patient_id).count()
    total_appointments = Appointment.query.filter_by(doctor_id=id).count()
    completed = Appointment.query.filter_by(doctor_id=id, status='completed').count()

    return render_template('doctors/view.html',
        doctor=doctor,
        upcoming=upcoming,
        total_patients=total_patients,
        total_appointments=total_appointments,
        completed=completed
    )


@doctors_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    doctor = Doctor.query.get_or_404(id)
    departments = Department.query.all()

    if request.method == 'POST':
        dept_id = request.form.get('department_id')
        doctor.first_name = request.form.get('first_name')
        doctor.last_name = request.form.get('last_name')
        doctor.specialization = request.form.get('specialization')
        doctor.department_id = int(dept_id) if dept_id else None
        doctor.phone = request.form.get('phone')
        doctor.email = request.form.get('email')
        doctor.license_number = request.form.get('license_number')
        doctor.qualification = request.form.get('qualification')
        doctor.experience_years = int(request.form.get('experience_years') or 0)
        doctor.consultation_fee = float(request.form.get('consultation_fee') or 0)
        doctor.available_days = request.form.get('available_days', 'Mon,Tue,Wed,Thu,Fri')
        doctor.available_from = request.form.get('available_from', '09:00')
        doctor.available_to = request.form.get('available_to', '17:00')
        doctor.status = request.form.get('status', 'active')
        db.session.commit()
        flash('Doctor profile updated successfully!', 'success')
        return redirect(url_for('doctors.view', id=doctor.id))

    return render_template('doctors/edit.html', doctor=doctor, departments=departments)


@doctors_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    doctor = Doctor.query.get_or_404(id)
    doctor.status = 'inactive'
    db.session.commit()
    flash(f'Dr. {doctor.first_name} {doctor.last_name} has been deactivated.', 'info')
    return redirect(url_for('doctors.index'))
