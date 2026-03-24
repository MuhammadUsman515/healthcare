from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, MedicalCertificate, Patient, Doctor
from datetime import datetime, date
import random, string

certificates_bp = Blueprint('certificates', __name__, url_prefix='/certificates')


def gen_cert_number(cert_type):
    prefix = {'fitness': 'FIT', 'sick_leave': 'SL', 'birth': 'BC', 'death': 'DC',
              'vaccination': 'VAC', 'disability': 'DIS'}.get(cert_type, 'CERT')
    return prefix + ''.join(random.choices(string.digits, k=5))


@certificates_bp.route('/')
@login_required
def index():
    type_filter = request.args.get('type', '')
    search = request.args.get('search', '')

    query = MedicalCertificate.query.filter_by(status='active')
    if type_filter:
        query = query.filter_by(cert_type=type_filter)
    if search:
        query = query.filter(
            (MedicalCertificate.cert_number.ilike(f'%{search}%')) |
            (MedicalCertificate.patient_name.ilike(f'%{search}%'))
        )

    certs = query.order_by(MedicalCertificate.created_at.desc()).all()

    cert_types = ['fitness', 'sick_leave', 'birth', 'death', 'vaccination', 'disability']
    type_labels = {'fitness': 'Fitness', 'sick_leave': 'Sick Leave',
                   'birth': 'Birth', 'death': 'Death',
                   'vaccination': 'Vaccination', 'disability': 'Disability'}

    return render_template('certificates/index.html',
        certs=certs, cert_types=cert_types, type_labels=type_labels,
        type_filter=type_filter, search=search
    )


@certificates_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    patients = Patient.query.filter_by(status='active').order_by(Patient.first_name).all()
    doctors = Doctor.query.filter_by(status='active').order_by(Doctor.first_name).all()

    if request.method == 'POST':
        cert_type = request.form.get('cert_type')
        patient_id = request.form.get('patient_id') or None
        doctor_id = request.form.get('doctor_id') or None

        patient_name = request.form.get('patient_name', '')
        if patient_id and not patient_name:
            p = Patient.query.get(int(patient_id))
            if p:
                patient_name = f'{p.first_name} {p.last_name}'

        valid_until_str = request.form.get('valid_until')
        valid_until = datetime.strptime(valid_until_str, '%Y-%m-%d').date() if valid_until_str else None

        rest_days_str = request.form.get('rest_days')
        rest_days = int(rest_days_str) if rest_days_str and rest_days_str.isdigit() else None

        cert = MedicalCertificate(
            cert_number=gen_cert_number(cert_type),
            cert_type=cert_type,
            patient_id=int(patient_id) if patient_id else None,
            doctor_id=int(doctor_id) if doctor_id else None,
            patient_name=patient_name,
            patient_age=request.form.get('patient_age', ''),
            patient_gender=request.form.get('patient_gender', ''),
            issue_date=date.today(),
            valid_until=valid_until,
            diagnosis=request.form.get('diagnosis', ''),
            purpose=request.form.get('purpose', ''),
            rest_days=rest_days,
            notes=request.form.get('notes', ''),
        )
        db.session.add(cert)
        db.session.commit()
        flash(f'Certificate {cert.cert_number} issued!', 'success')
        return redirect(url_for('certificates.view', id=cert.id))

    # Pre-fill from patient_id query param
    prefill_patient = None
    pid = request.args.get('patient_id')
    if pid:
        prefill_patient = Patient.query.get(int(pid))

    cert_type_default = request.args.get('type', 'fitness')

    return render_template('certificates/new.html',
        patients=patients, doctors=doctors,
        today=date.today(),
        cert_type_default=cert_type_default,
        prefill_patient=prefill_patient
    )


@certificates_bp.route('/<int:id>')
@login_required
def view(id):
    cert = MedicalCertificate.query.get_or_404(id)
    return render_template('certificates/view.html', cert=cert)


@certificates_bp.route('/<int:id>/print')
@login_required
def print_cert(id):
    cert = MedicalCertificate.query.get_or_404(id)
    return render_template('certificates/print.html', cert=cert)


@certificates_bp.route('/<int:id>/cancel', methods=['POST'])
@login_required
def cancel(id):
    cert = MedicalCertificate.query.get_or_404(id)
    cert.status = 'cancelled'
    db.session.commit()
    flash(f'Certificate {cert.cert_number} cancelled.', 'warning')
    return redirect(url_for('certificates.index'))
