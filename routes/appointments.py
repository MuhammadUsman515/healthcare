from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from models import db, Appointment, Patient, Doctor, MedicalRecord, Prescription, LabTest
from datetime import datetime, date
import random
import string

appointments_bp = Blueprint('appointments', __name__, url_prefix='/appointments')


def generate_appointment_id():
    return 'APT' + ''.join(random.choices(string.digits, k=6))


@appointments_bp.route('/')
@login_required
def index():
    filter_date = request.args.get('date', '')
    status = request.args.get('status', 'all')
    doctor_id = request.args.get('doctor', '')

    query = Appointment.query
    if filter_date:
        query = query.filter_by(appointment_date=datetime.strptime(filter_date, '%Y-%m-%d').date())
    else:
        # Default to today
        query = query.filter_by(appointment_date=date.today())
        filter_date = date.today().strftime('%Y-%m-%d')

    if status != 'all':
        query = query.filter_by(status=status)
    if doctor_id:
        query = query.filter_by(doctor_id=int(doctor_id))

    appointments = query.order_by(Appointment.appointment_time).all()
    doctors = Doctor.query.filter_by(status='active').all()

    return render_template('appointments/index.html',
        appointments=appointments,
        doctors=doctors,
        filter_date=filter_date,
        status=status,
        doctor_id=doctor_id
    )


@appointments_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    patients = Patient.query.filter_by(status='active').order_by(Patient.first_name).all()
    doctors = Doctor.query.filter_by(status='active').order_by(Doctor.first_name).all()

    if request.method == 'POST':
        apt_date = datetime.strptime(request.form.get('appointment_date'), '%Y-%m-%d').date()
        appointment = Appointment(
            appointment_id=generate_appointment_id(),
            patient_id=int(request.form.get('patient_id')),
            doctor_id=int(request.form.get('doctor_id')),
            appointment_date=apt_date,
            appointment_time=request.form.get('appointment_time'),
            reason=request.form.get('reason'),
            notes=request.form.get('notes'),
        )
        db.session.add(appointment)
        db.session.commit()
        flash(f'Appointment {appointment.appointment_id} scheduled successfully!', 'success')
        return redirect(url_for('appointments.view', id=appointment.id))

    # Pre-select patient if provided
    patient_id = request.args.get('patient_id')
    return render_template('appointments/new.html', patients=patients, doctors=doctors, patient_id=patient_id)


@appointments_bp.route('/<int:id>')
@login_required
def view(id):
    appointment = Appointment.query.get_or_404(id)
    medical_record = MedicalRecord.query.filter_by(appointment_id=id).first()
    return render_template('appointments/view.html', appointment=appointment, medical_record=medical_record)


@appointments_bp.route('/<int:id>/status', methods=['POST'])
@login_required
def update_status(id):
    appointment = Appointment.query.get_or_404(id)
    new_status = request.form.get('status')
    appointment.status = new_status
    db.session.commit()
    flash(f'Appointment status updated to {new_status}.', 'success')
    return redirect(url_for('appointments.view', id=id))


@appointments_bp.route('/<int:id>/record', methods=['GET', 'POST'])
@login_required
def add_record(id):
    appointment = Appointment.query.get_or_404(id)

    if request.method == 'POST':
        record = MedicalRecord(
            patient_id=appointment.patient_id,
            doctor_id=appointment.doctor_id,
            appointment_id=appointment.id,
            chief_complaint=request.form.get('chief_complaint'),
            diagnosis=request.form.get('diagnosis'),
            treatment_plan=request.form.get('treatment_plan'),
            vitals_bp=request.form.get('vitals_bp'),
            vitals_pulse=request.form.get('vitals_pulse'),
            vitals_temperature=request.form.get('vitals_temperature'),
            vitals_weight=request.form.get('vitals_weight'),
            vitals_height=request.form.get('vitals_height'),
            vitals_oxygen=request.form.get('vitals_oxygen'),
            notes=request.form.get('notes'),
        )
        follow_up = request.form.get('follow_up_date')
        if follow_up:
            record.follow_up_date = datetime.strptime(follow_up, '%Y-%m-%d').date()

        db.session.add(record)
        db.session.flush()

        # Add prescriptions
        medicine_names = request.form.getlist('medicine_name[]')
        dosages = request.form.getlist('dosage[]')
        frequencies = request.form.getlist('frequency[]')
        durations = request.form.getlist('duration[]')
        instructions_list = request.form.getlist('instructions[]')

        for i, med in enumerate(medicine_names):
            if med.strip():
                p = Prescription(
                    medical_record_id=record.id,
                    medicine_name=med,
                    dosage=dosages[i] if i < len(dosages) else '',
                    frequency=frequencies[i] if i < len(frequencies) else '',
                    duration=durations[i] if i < len(durations) else '',
                    instructions=instructions_list[i] if i < len(instructions_list) else '',
                )
                db.session.add(p)

        # Add lab tests
        test_names = request.form.getlist('test_name[]')
        for test in test_names:
            if test.strip():
                lt = LabTest(medical_record_id=record.id, test_name=test)
                db.session.add(lt)

        appointment.status = 'completed'
        db.session.commit()
        flash('Medical record saved successfully!', 'success')
        return redirect(url_for('appointments.view', id=id))

    return render_template('appointments/add_record.html', appointment=appointment)


@appointments_bp.route('/calendar')
@login_required
def calendar():
    doctors = Doctor.query.filter_by(status='active').all()
    return render_template('appointments/calendar.html', doctors=doctors)
