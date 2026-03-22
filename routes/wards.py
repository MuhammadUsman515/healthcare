from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from models import db, Ward, Bed, Admission, Patient, Doctor, Department
from datetime import datetime
import random
import string

wards_bp = Blueprint('wards', __name__, url_prefix='/wards')


def generate_admission_id():
    return 'ADM' + ''.join(random.choices(string.digits, k=6))


@wards_bp.route('/')
@login_required
def index():
    wards = Ward.query.all()
    total_beds = Bed.query.count()
    available_beds = Bed.query.filter_by(status='available').count()
    occupied_beds = Bed.query.filter_by(status='occupied').count()
    return render_template('wards/index.html',
        wards=wards,
        total_beds=total_beds,
        available_beds=available_beds,
        occupied_beds=occupied_beds
    )


@wards_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_ward():
    departments = Department.query.all()

    if request.method == 'POST':
        ward = Ward(
            name=request.form.get('name'),
            department_id=int(request.form.get('department_id')) if request.form.get('department_id') else None,
            ward_type=request.form.get('ward_type'),
            total_beds=int(request.form.get('total_beds') or 0),
        )
        db.session.add(ward)
        db.session.flush()

        # Create beds
        num_beds = int(request.form.get('total_beds') or 0)
        daily_rate = float(request.form.get('daily_rate') or 0)
        for i in range(1, num_beds + 1):
            bed = Bed(
                bed_number=f'{ward.name[:3].upper()}-{i:02d}',
                ward_id=ward.id,
                daily_rate=daily_rate
            )
            db.session.add(bed)

        db.session.commit()
        flash(f'Ward {ward.name} created with {num_beds} beds!', 'success')
        return redirect(url_for('wards.index'))

    return render_template('wards/new_ward.html', departments=departments)


@wards_bp.route('/<int:id>')
@login_required
def view_ward(id):
    ward = Ward.query.get_or_404(id)
    return render_template('wards/view_ward.html', ward=ward)


@wards_bp.route('/admissions')
@login_required
def admissions():
    status = request.args.get('status', 'admitted')
    query = Admission.query
    if status != 'all':
        query = query.filter_by(status=status)
    admissions = query.order_by(Admission.admission_date.desc()).all()
    return render_template('wards/admissions.html', admissions=admissions, status=status)


@wards_bp.route('/admit', methods=['GET', 'POST'])
@login_required
def admit_patient():
    patients = Patient.query.filter_by(status='active').order_by(Patient.first_name).all()
    doctors = Doctor.query.filter_by(status='active').order_by(Doctor.first_name).all()
    available_beds = Bed.query.filter_by(status='available').all()

    if request.method == 'POST':
        bed_id = request.form.get('bed_id')
        admission = Admission(
            admission_id=generate_admission_id(),
            patient_id=int(request.form.get('patient_id')),
            bed_id=int(bed_id) if bed_id else None,
            admitting_doctor_id=int(request.form.get('doctor_id')) if request.form.get('doctor_id') else None,
            diagnosis=request.form.get('diagnosis'),
            notes=request.form.get('notes'),
        )
        db.session.add(admission)

        if bed_id:
            bed = Bed.query.get(int(bed_id))
            if bed:
                bed.status = 'occupied'

        db.session.commit()
        flash(f'Patient admitted successfully! Admission ID: {admission.admission_id}', 'success')
        return redirect(url_for('wards.admissions'))

    return render_template('wards/admit.html', patients=patients, doctors=doctors, available_beds=available_beds)


@wards_bp.route('/admissions/<int:id>/discharge', methods=['POST'])
@login_required
def discharge(id):
    admission = Admission.query.get_or_404(id)
    admission.status = 'discharged'
    admission.discharge_date = datetime.utcnow()

    if admission.bed_id:
        bed = Bed.query.get(admission.bed_id)
        if bed:
            bed.status = 'available'

    db.session.commit()
    flash(f'Patient {admission.patient.full_name} discharged successfully!', 'success')
    return redirect(url_for('wards.admissions'))
