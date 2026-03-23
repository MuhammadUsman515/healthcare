from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from models import db, Referral, Patient, Doctor, Department
from datetime import datetime, date
import random
import string

referrals_bp = Blueprint('referrals', __name__, url_prefix='/referrals')


def generate_referral_number():
    return 'REF' + ''.join(random.choices(string.digits, k=6))


@referrals_bp.route('/')
@login_required
def index():
    status = request.args.get('status', 'all')
    query = Referral.query
    if status != 'all':
        query = query.filter_by(status=status)
    referrals = query.order_by(Referral.referral_date.desc()).all()
    return render_template('referrals/index.html', referrals=referrals, status=status)


@referrals_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    patients = Patient.query.filter_by(status='active').order_by(Patient.first_name).all()
    doctors = Doctor.query.filter_by(status='active').order_by(Doctor.first_name).all()
    departments = Department.query.all()
    if request.method == 'POST':
        apt_date_str = request.form.get('appointment_date')
        ref = Referral(
            referral_number=generate_referral_number(),
            patient_id=int(request.form.get('patient_id')),
            referring_doctor_id=int(request.form.get('referring_doctor_id')),
            referred_to_doctor_id=request.form.get('referred_to_doctor_id') or None,
            referred_to_department_id=request.form.get('referred_to_department_id') or None,
            referred_to_hospital=request.form.get('referred_to_hospital'),
            reason=request.form.get('reason'),
            urgency=request.form.get('urgency', 'routine'),
            referral_date=date.today(),
            appointment_date=datetime.strptime(apt_date_str, '%Y-%m-%d').date() if apt_date_str else None,
            notes=request.form.get('notes'),
        )
        db.session.add(ref)
        db.session.commit()
        flash(f'Referral {ref.referral_number} created successfully!', 'success')
        return redirect(url_for('referrals.index'))
    return render_template('referrals/new.html', patients=patients, doctors=doctors, departments=departments)


@referrals_bp.route('/<int:id>')
@login_required
def view(id):
    referral = Referral.query.get_or_404(id)
    return render_template('referrals/view.html', referral=referral)


@referrals_bp.route('/<int:id>/update', methods=['POST'])
@login_required
def update_status(id):
    referral = Referral.query.get_or_404(id)
    referral.status = request.form.get('status', referral.status)
    db.session.commit()
    flash('Referral status updated.', 'success')
    return redirect(url_for('referrals.view', id=referral.id))
