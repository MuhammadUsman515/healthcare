from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from models import db, Ambulance, AmbulanceDispatch, Patient
from datetime import datetime
import random
import string

ambulance_bp = Blueprint('ambulance', __name__, url_prefix='/ambulance')


def generate_dispatch_number():
    return 'DISP' + ''.join(random.choices(string.digits, k=5))


@ambulance_bp.route('/')
@ambulance_bp.route('/fleet')
@login_required
def index():
    ambulances = Ambulance.query.order_by(Ambulance.vehicle_number).all()
    available = sum(1 for a in ambulances if a.status == 'available')
    dispatched = sum(1 for a in ambulances if a.status == 'dispatched')
    maintenance = sum(1 for a in ambulances if a.status == 'maintenance')
    recent_dispatches = AmbulanceDispatch.query.order_by(AmbulanceDispatch.dispatch_time.desc()).limit(5).all()
    return render_template('ambulance/index.html', ambulances=ambulances,
                           available=available, dispatched=dispatched, maintenance=maintenance,
                           recent_dispatches=recent_dispatches)


@ambulance_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        svc_str = request.form.get('last_service_date')
        ambulance = Ambulance(
            vehicle_number=request.form.get('vehicle_number'),
            vehicle_type=request.form.get('vehicle_type'),
            driver_name=request.form.get('driver_name'),
            driver_phone=request.form.get('driver_phone'),
            status=request.form.get('status', 'available'),
            last_service_date=datetime.strptime(svc_str, '%Y-%m-%d').date() if svc_str else None,
            equipment=request.form.get('equipment'),
        )
        db.session.add(ambulance)
        db.session.commit()
        flash(f'Ambulance {ambulance.vehicle_number} registered successfully!', 'success')
        return redirect(url_for('ambulance.index'))
    return render_template('ambulance/new.html')


@ambulance_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    amb = Ambulance.query.get_or_404(id)
    if request.method == 'POST':
        svc_str = request.form.get('last_service_date')
        amb.vehicle_number = request.form.get('vehicle_number')
        amb.vehicle_type = request.form.get('vehicle_type')
        amb.driver_name = request.form.get('driver_name')
        amb.driver_phone = request.form.get('driver_phone')
        amb.status = request.form.get('status')
        amb.last_service_date = datetime.strptime(svc_str, '%Y-%m-%d').date() if svc_str else amb.last_service_date
        amb.equipment = request.form.get('equipment')
        db.session.commit()
        flash('Ambulance updated successfully!', 'success')
        return redirect(url_for('ambulance.index'))
    return render_template('ambulance/edit.html', amb=amb)


@ambulance_bp.route('/dispatch/new', methods=['GET', 'POST'])
@login_required
def new_dispatch():
    available_ambs = Ambulance.query.filter_by(status='available').all()
    patients = Patient.query.filter_by(status='active').order_by(Patient.first_name).all()
    if request.method == 'POST':
        amb_id = int(request.form.get('ambulance_id'))
        amb = Ambulance.query.get(amb_id)
        if not amb or amb.status != 'available':
            flash('Selected ambulance is not available.', 'danger')
            return redirect(url_for('ambulance.new_dispatch'))

        dispatch = AmbulanceDispatch(
            dispatch_number=generate_dispatch_number(),
            ambulance_id=amb_id,
            patient_id=request.form.get('patient_id') or None,
            pickup_address=request.form.get('pickup_address'),
            destination=request.form.get('destination'),
            caller_name=request.form.get('caller_name'),
            caller_phone=request.form.get('caller_phone'),
            dispatch_time=datetime.utcnow(),
            notes=request.form.get('notes'),
        )
        amb.status = 'dispatched'
        db.session.add(dispatch)
        db.session.commit()
        flash(f'Ambulance {amb.vehicle_number} dispatched. Dispatch #: {dispatch.dispatch_number}', 'success')
        return redirect(url_for('ambulance.dispatches'))
    return render_template('ambulance/new_dispatch.html', available_ambs=available_ambs, patients=patients)


@ambulance_bp.route('/dispatches')
@login_required
def dispatches():
    status = request.args.get('status', 'all')
    query = AmbulanceDispatch.query
    if status != 'all':
        query = query.filter_by(status=status)
    dispatches = query.order_by(AmbulanceDispatch.dispatch_time.desc()).all()
    return render_template('ambulance/dispatches.html', dispatches=dispatches, status=status)


@ambulance_bp.route('/dispatches/<int:id>/complete', methods=['POST'])
@login_required
def complete_dispatch(id):
    dispatch = AmbulanceDispatch.query.get_or_404(id)
    dispatch.status = 'completed'
    dispatch.arrival_time = datetime.utcnow()
    if dispatch.ambulance:
        dispatch.ambulance.status = 'available'
    db.session.commit()
    flash('Dispatch marked as completed. Ambulance is now available.', 'success')
    return redirect(url_for('ambulance.dispatches'))
