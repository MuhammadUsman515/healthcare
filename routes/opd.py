from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from models import db, OPDQueue, Patient, Doctor, Department
from datetime import datetime, date

opd_bp = Blueprint('opd', __name__, url_prefix='/opd')


def next_token(queue_date):
    last = OPDQueue.query.filter_by(queue_date=queue_date).order_by(OPDQueue.token_number.desc()).first()
    return (last.token_number + 1) if last else 1


@opd_bp.route('/')
@login_required
def index():
    today = date.today()
    queue_date_str = request.args.get('date', today.strftime('%Y-%m-%d'))
    try:
        queue_date = datetime.strptime(queue_date_str, '%Y-%m-%d').date()
    except ValueError:
        queue_date = today

    dept_filter = request.args.get('department', 'all')
    query = OPDQueue.query.filter_by(queue_date=queue_date)
    if dept_filter != 'all':
        query = query.filter_by(department_id=int(dept_filter))

    queue = query.order_by(OPDQueue.token_number).all()
    departments = Department.query.all()
    waiting = sum(1 for q in queue if q.status == 'waiting')
    in_consult = sum(1 for q in queue if q.status == 'in_consultation')
    completed = sum(1 for q in queue if q.status == 'completed')
    return render_template('opd/index.html', queue=queue, departments=departments,
                           queue_date=queue_date, dept_filter=dept_filter,
                           waiting=waiting, in_consult=in_consult, completed=completed)


@opd_bp.route('/checkin', methods=['GET', 'POST'])
@login_required
def checkin():
    patients = Patient.query.filter_by(status='active').order_by(Patient.first_name).all()
    doctors = Doctor.query.filter_by(status='active').order_by(Doctor.first_name).all()
    departments = Department.query.all()
    if request.method == 'POST':
        today = date.today()
        token = next_token(today)
        entry = OPDQueue(
            token_number=token,
            patient_id=int(request.form.get('patient_id')),
            doctor_id=request.form.get('doctor_id') or None,
            department_id=request.form.get('department_id') or None,
            priority=request.form.get('priority', 'normal'),
            reason=request.form.get('reason'),
            queue_date=today,
            check_in_time=datetime.utcnow(),
        )
        db.session.add(entry)
        db.session.commit()
        flash(f'Patient checked in. Token Number: {token}', 'success')
        return redirect(url_for('opd.index'))
    return render_template('opd/checkin.html', patients=patients, doctors=doctors, departments=departments)


@opd_bp.route('/<int:id>/call', methods=['POST'])
@login_required
def call_patient(id):
    entry = OPDQueue.query.get_or_404(id)
    entry.status = 'in_consultation'
    entry.consultation_start = datetime.utcnow()
    db.session.commit()
    flash(f'Token {entry.token_number} called for consultation.', 'info')
    return redirect(url_for('opd.index'))


@opd_bp.route('/<int:id>/complete', methods=['POST'])
@login_required
def complete(id):
    entry = OPDQueue.query.get_or_404(id)
    entry.status = 'completed'
    entry.consultation_end = datetime.utcnow()
    entry.notes = request.form.get('notes', entry.notes)
    db.session.commit()
    flash(f'Token {entry.token_number} consultation completed.', 'success')
    return redirect(url_for('opd.index'))


@opd_bp.route('/<int:id>/cancel', methods=['POST'])
@login_required
def cancel(id):
    entry = OPDQueue.query.get_or_404(id)
    entry.status = 'cancelled'
    db.session.commit()
    flash(f'Token {entry.token_number} cancelled.', 'info')
    return redirect(url_for('opd.index'))
