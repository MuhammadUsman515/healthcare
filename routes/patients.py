from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from models import db, Patient, Appointment, MedicalRecord, Bill, Admission
from datetime import datetime, date
import random
import string

patients_bp = Blueprint('patients', __name__, url_prefix='/patients')


def generate_patient_id():
    return 'P' + ''.join(random.choices(string.digits, k=6))


@patients_bp.route('/')
@login_required
def index():
    search = request.args.get('search', '')
    status = request.args.get('status', 'all')

    query = Patient.query
    if search:
        query = query.filter(
            (Patient.first_name.ilike(f'%{search}%')) |
            (Patient.last_name.ilike(f'%{search}%')) |
            (Patient.patient_id.ilike(f'%{search}%')) |
            (Patient.phone.ilike(f'%{search}%'))
        )
    if status != 'all':
        query = query.filter_by(status=status)

    patients = query.order_by(Patient.created_at.desc()).all()
    return render_template('patients/index.html', patients=patients, search=search, status=status)


@patients_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        dob_str = request.form.get('date_of_birth')
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None

        patient = Patient(
            patient_id=generate_patient_id(),
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            date_of_birth=dob,
            gender=request.form.get('gender'),
            blood_group=request.form.get('blood_group'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            address=request.form.get('address'),
            emergency_contact_name=request.form.get('emergency_contact_name'),
            emergency_contact_phone=request.form.get('emergency_contact_phone'),
            emergency_contact_relation=request.form.get('emergency_contact_relation'),
            allergies=request.form.get('allergies'),
            chronic_conditions=request.form.get('chronic_conditions'),
            insurance_provider=request.form.get('insurance_provider'),
            insurance_number=request.form.get('insurance_number'),
        )
        db.session.add(patient)
        db.session.commit()
        flash(f'Patient {patient.full_name} registered successfully! ID: {patient.patient_id}', 'success')
        return redirect(url_for('patients.view', id=patient.id))

    return render_template('patients/new.html')


@patients_bp.route('/<int:id>')
@login_required
def view(id):
    patient = Patient.query.get_or_404(id)
    appointments = Appointment.query.filter_by(patient_id=id).order_by(Appointment.appointment_date.desc()).all()
    medical_records = MedicalRecord.query.filter_by(patient_id=id).order_by(MedicalRecord.visit_date.desc()).all()
    bills = Bill.query.filter_by(patient_id=id).order_by(Bill.bill_date.desc()).all()
    admissions = Admission.query.filter_by(patient_id=id).order_by(Admission.admission_date.desc()).all()
    return render_template('patients/view.html',
        patient=patient,
        appointments=appointments,
        medical_records=medical_records,
        bills=bills,
        admissions=admissions
    )


@patients_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    patient = Patient.query.get_or_404(id)

    if request.method == 'POST':
        dob_str = request.form.get('date_of_birth')
        patient.first_name = request.form.get('first_name')
        patient.last_name = request.form.get('last_name')
        patient.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else patient.date_of_birth
        patient.gender = request.form.get('gender')
        patient.blood_group = request.form.get('blood_group')
        patient.phone = request.form.get('phone')
        patient.email = request.form.get('email')
        patient.address = request.form.get('address')
        patient.emergency_contact_name = request.form.get('emergency_contact_name')
        patient.emergency_contact_phone = request.form.get('emergency_contact_phone')
        patient.emergency_contact_relation = request.form.get('emergency_contact_relation')
        patient.allergies = request.form.get('allergies')
        patient.chronic_conditions = request.form.get('chronic_conditions')
        patient.insurance_provider = request.form.get('insurance_provider')
        patient.insurance_number = request.form.get('insurance_number')
        patient.status = request.form.get('status', 'active')
        db.session.commit()
        flash('Patient information updated successfully!', 'success')
        return redirect(url_for('patients.view', id=patient.id))

    return render_template('patients/edit.html', patient=patient)


@patients_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    patient = Patient.query.get_or_404(id)
    patient.status = 'inactive'
    db.session.commit()
    flash(f'Patient {patient.full_name} has been deactivated.', 'info')
    return redirect(url_for('patients.index'))
