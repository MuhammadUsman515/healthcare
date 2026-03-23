from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from models import db, BloodInventory, BloodRequest, Patient, Doctor
from datetime import datetime, date
import random
import string

blood_bank_bp = Blueprint('blood_bank', __name__, url_prefix='/blood-bank')

BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-']


def generate_request_number():
    return 'BBR' + ''.join(random.choices(string.digits, k=6))


def ensure_inventory():
    for bg in BLOOD_GROUPS:
        if not BloodInventory.query.filter_by(blood_group=bg).first():
            inv = BloodInventory(blood_group=bg, units_available=0, units_reserved=0)
            db.session.add(inv)
    db.session.commit()


@blood_bank_bp.route('/')
@login_required
def index():
    ensure_inventory()
    inventory = BloodInventory.query.order_by(BloodInventory.blood_group).all()
    pending_requests = BloodRequest.query.filter_by(status='pending').order_by(BloodRequest.request_date.desc()).all()
    recent_requests = BloodRequest.query.order_by(BloodRequest.request_date.desc()).limit(10).all()
    return render_template('blood_bank/index.html', inventory=inventory,
                           pending_requests=pending_requests, recent_requests=recent_requests)


@blood_bank_bp.route('/update-stock', methods=['POST'])
@login_required
def update_stock():
    blood_group = request.form.get('blood_group')
    units = int(request.form.get('units', 0))
    inv = BloodInventory.query.filter_by(blood_group=blood_group).first()
    if inv:
        inv.units_available += units
        inv.last_updated = datetime.utcnow()
        db.session.commit()
        flash(f'Added {units} units of {blood_group} blood. Total: {inv.units_available} units.', 'success')
    return redirect(url_for('blood_bank.index'))


@blood_bank_bp.route('/requests')
@login_required
def requests_list():
    status = request.args.get('status', 'all')
    query = BloodRequest.query
    if status != 'all':
        query = query.filter_by(status=status)
    requests = query.order_by(BloodRequest.request_date.desc()).all()
    return render_template('blood_bank/requests.html', requests=requests, status=status)


@blood_bank_bp.route('/requests/new', methods=['GET', 'POST'])
@login_required
def new_request():
    patients = Patient.query.filter_by(status='active').order_by(Patient.first_name).all()
    doctors = Doctor.query.filter_by(status='active').order_by(Doctor.first_name).all()
    if request.method == 'POST':
        request_date_str = request.form.get('request_date')
        req = BloodRequest(
            request_number=generate_request_number(),
            patient_id=int(request.form.get('patient_id')),
            doctor_id=int(request.form.get('doctor_id')),
            blood_group=request.form.get('blood_group'),
            units_required=int(request.form.get('units_required', 1)),
            purpose=request.form.get('purpose'),
            urgency=request.form.get('urgency', 'normal'),
            request_date=datetime.strptime(request_date_str, '%Y-%m-%d').date() if request_date_str else date.today(),
            notes=request.form.get('notes'),
        )
        db.session.add(req)
        db.session.commit()
        flash(f'Blood request {req.request_number} created successfully!', 'success')
        return redirect(url_for('blood_bank.requests_list'))
    return render_template('blood_bank/new_request.html', patients=patients, doctors=doctors,
                           blood_groups=BLOOD_GROUPS, today=date.today())


@blood_bank_bp.route('/requests/<int:id>/approve', methods=['POST'])
@login_required
def approve_request(id):
    req = BloodRequest.query.get_or_404(id)
    inv = BloodInventory.query.filter_by(blood_group=req.blood_group).first()
    units_to_issue = int(request.form.get('units_issued', req.units_required))

    if not inv or inv.units_available < units_to_issue:
        flash(f'Insufficient {req.blood_group} blood units in stock.', 'danger')
        return redirect(url_for('blood_bank.requests_list'))

    inv.units_available -= units_to_issue
    inv.last_updated = datetime.utcnow()
    req.units_issued = units_to_issue
    req.status = 'issued'
    req.issue_date = date.today()
    db.session.commit()
    flash(f'Blood request approved. {units_to_issue} units of {req.blood_group} issued.', 'success')
    return redirect(url_for('blood_bank.requests_list'))


@blood_bank_bp.route('/requests/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_request(id):
    req = BloodRequest.query.get_or_404(id)
    req.status = 'cancelled'
    db.session.commit()
    flash('Blood request cancelled.', 'info')
    return redirect(url_for('blood_bank.requests_list'))
