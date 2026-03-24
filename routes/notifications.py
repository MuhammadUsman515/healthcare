"""
Notification & Reminder Engine
- Appointment reminders
- Follow-up due alerts
- Bill due reminders
- Welcome messages
- WhatsApp/SMS/Email simulation (pluggable backend)
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import (db, Organization, NotificationTemplate, NotificationLog,
                    ScheduledReminder, Patient, Appointment, Bill, MedicalRecord,
                    FollowUpTask, User)
from datetime import datetime, date, timedelta

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')


def get_org_id():
    return current_user.org_id if current_user.is_authenticated else None


def send_notification(channel, recipient, message, patient_id=None, org_id=None,
                      event_type='manual', template_id=None):
    """
    Pluggable notification sender.
    Replace the body of each channel with actual Twilio/WhatsApp/SMTP calls.
    """
    status = 'sent'
    error = None

    if channel == 'sms':
        # TODO: Twilio SMS
        # from twilio.rest import Client
        # client = Client(TWILIO_SID, TWILIO_TOKEN)
        # client.messages.create(to=recipient, from_=TWILIO_FROM, body=message)
        status = 'sent'  # simulate success

    elif channel == 'whatsapp':
        # TODO: Twilio WhatsApp or Meta WhatsApp Business API
        status = 'sent'

    elif channel == 'email':
        # TODO: SMTP / SendGrid
        status = 'sent'

    # Log the notification
    log = NotificationLog(
        org_id=org_id,
        template_id=template_id,
        patient_id=patient_id,
        event_type=event_type,
        channel=channel,
        recipient=recipient,
        message=message,
        status=status,
        error_message=error,
    )
    db.session.add(log)
    db.session.commit()
    return status


def render_template_body(body, context):
    """Replace {{placeholder}} tokens with context values."""
    for key, val in context.items():
        body = body.replace(f'{{{{{key}}}}}', str(val))
    return body


# ── Dashboard ─────────────────────────────────────────────────────────────────

@notifications_bp.route('/')
@login_required
def index():
    org_id = get_org_id()
    templates = NotificationTemplate.query.filter_by(org_id=org_id).order_by(
        NotificationTemplate.created_at.desc()
    ).all()
    recent_logs = NotificationLog.query.filter_by(org_id=org_id).order_by(
        NotificationLog.sent_at.desc()
    ).limit(50).all()
    pending_reminders = ScheduledReminder.query.filter_by(
        org_id=org_id, status='pending'
    ).count()

    return render_template('notifications/index.html',
        templates=templates, recent_logs=recent_logs, pending_reminders=pending_reminders)


# ── Templates CRUD ────────────────────────────────────────────────────────────

@notifications_bp.route('/templates/new', methods=['GET', 'POST'])
@login_required
def new_template():
    org_id = get_org_id()
    if request.method == 'POST':
        tmpl = NotificationTemplate(
            org_id=org_id,
            name=request.form.get('name'),
            event_type=request.form.get('event_type'),
            channel=request.form.get('channel', 'sms'),
            subject=request.form.get('subject'),
            body=request.form.get('body'),
            send_before_hours=int(request.form.get('send_before_hours', 24)),
        )
        db.session.add(tmpl)
        db.session.commit()
        flash('Template created!', 'success')
        return redirect(url_for('notifications.index'))

    return render_template('notifications/template_form.html', tmpl=None)


@notifications_bp.route('/templates/<int:tid>/edit', methods=['GET', 'POST'])
@login_required
def edit_template(tid):
    org_id = get_org_id()
    tmpl = NotificationTemplate.query.filter_by(id=tid, org_id=org_id).first_or_404()
    if request.method == 'POST':
        tmpl.name = request.form.get('name', tmpl.name)
        tmpl.channel = request.form.get('channel', tmpl.channel)
        tmpl.subject = request.form.get('subject', tmpl.subject)
        tmpl.body = request.form.get('body', tmpl.body)
        tmpl.send_before_hours = int(request.form.get('send_before_hours', tmpl.send_before_hours))
        tmpl.is_active = request.form.get('is_active') == 'on'
        db.session.commit()
        flash('Template updated!', 'success')
        return redirect(url_for('notifications.index'))

    return render_template('notifications/template_form.html', tmpl=tmpl)


@notifications_bp.route('/templates/<int:tid>/toggle', methods=['POST'])
@login_required
def toggle_template(tid):
    org_id = get_org_id()
    tmpl = NotificationTemplate.query.filter_by(id=tid, org_id=org_id).first_or_404()
    tmpl.is_active = not tmpl.is_active
    db.session.commit()
    return jsonify({'active': tmpl.is_active})


# ── Send Manual Notification ──────────────────────────────────────────────────

@notifications_bp.route('/send', methods=['GET', 'POST'])
@login_required
def send_manual():
    org_id = get_org_id()
    if request.method == 'POST':
        patient_id = request.form.get('patient_id')
        channel = request.form.get('channel', 'sms')
        message = request.form.get('message', '').strip()
        recipient = request.form.get('recipient', '').strip()

        patient = Patient.query.filter_by(id=patient_id, org_id=org_id).first() if patient_id else None
        if patient and not recipient:
            recipient = patient.phone

        if not recipient or not message:
            flash('Recipient and message are required.', 'danger')
            return redirect(url_for('notifications.send_manual'))

        status = send_notification(
            channel=channel,
            recipient=recipient,
            message=message,
            patient_id=patient.id if patient else None,
            org_id=org_id,
            event_type='manual',
        )
        flash(f'Notification {status}!', 'success')
        return redirect(url_for('notifications.index'))

    patients = Patient.query.filter_by(org_id=org_id).order_by(Patient.first_name).limit(100).all()
    return render_template('notifications/send_manual.html', patients=patients)


# ── Bulk Reminder Dispatcher ──────────────────────────────────────────────────

@notifications_bp.route('/dispatch/appointment-reminders', methods=['POST'])
@login_required
def dispatch_appointment_reminders():
    """Send reminders for tomorrow's appointments."""
    org_id = get_org_id()
    tomorrow = date.today() + timedelta(days=1)

    template = NotificationTemplate.query.filter_by(
        org_id=org_id, event_type='appointment_reminder', is_active=True
    ).first()

    if not template:
        flash('No active appointment reminder template found. Create one first.', 'warning')
        return redirect(url_for('notifications.index'))

    appointments = Appointment.query.filter_by(
        org_id=org_id, appointment_date=tomorrow
    ).filter(Appointment.status.in_(['scheduled'])).all()

    sent = 0
    for appt in appointments:
        patient = appt.patient
        if not patient or not patient.phone:
            continue
        context = {
            'patient_name': patient.full_name,
            'doctor_name': appt.doctor.full_name if appt.doctor else 'your doctor',
            'appointment_date': str(appt.appointment_date),
            'appointment_time': appt.appointment_time,
        }
        body = render_template_body(template.body, context)
        send_notification(
            channel=template.channel,
            recipient=patient.phone,
            message=body,
            patient_id=patient.id,
            org_id=org_id,
            event_type='appointment_reminder',
            template_id=template.id,
        )
        sent += 1

    flash(f'{sent} appointment reminder(s) sent for tomorrow.', 'success')
    return redirect(url_for('notifications.index'))


@notifications_bp.route('/dispatch/follow-up-reminders', methods=['POST'])
@login_required
def dispatch_follow_up_reminders():
    """Send reminders for overdue/due follow-ups."""
    org_id = get_org_id()
    today = date.today()

    template = NotificationTemplate.query.filter_by(
        org_id=org_id, event_type='follow_up_due', is_active=True
    ).first()

    if not template:
        flash('No active follow-up reminder template.', 'warning')
        return redirect(url_for('notifications.index'))

    # Find medical records with due follow-ups
    due_records = MedicalRecord.query.filter(
        MedicalRecord.org_id == org_id,
        MedicalRecord.follow_up_date <= today,
        MedicalRecord.follow_up_date.isnot(None),
    ).all()

    sent = 0
    notified_patients = set()
    for record in due_records:
        patient = record.patient
        if not patient or not patient.phone or patient.id in notified_patients:
            continue
        context = {
            'patient_name': patient.full_name,
            'doctor_name': record.doctor.full_name if record.doctor else 'your doctor',
            'follow_up_date': str(record.follow_up_date),
        }
        body = render_template_body(template.body, context)
        send_notification(
            channel=template.channel,
            recipient=patient.phone,
            message=body,
            patient_id=patient.id,
            org_id=org_id,
            event_type='follow_up_due',
            template_id=template.id,
        )
        notified_patients.add(patient.id)
        sent += 1

    flash(f'{sent} follow-up reminder(s) sent.', 'success')
    return redirect(url_for('notifications.index'))


@notifications_bp.route('/dispatch/bill-reminders', methods=['POST'])
@login_required
def dispatch_bill_reminders():
    """Send reminders for overdue bills."""
    org_id = get_org_id()
    today = date.today()

    template = NotificationTemplate.query.filter_by(
        org_id=org_id, event_type='bill_due', is_active=True
    ).first()

    if not template:
        flash('No active bill reminder template.', 'warning')
        return redirect(url_for('notifications.index'))

    overdue_bills = Bill.query.filter(
        Bill.org_id == org_id,
        Bill.payment_status.in_(['pending', 'partial']),
        Bill.due_date <= today,
        Bill.due_date.isnot(None),
    ).all()

    sent = 0
    notified_patients = set()
    for bill in overdue_bills:
        patient = bill.patient
        if not patient or not patient.phone or patient.id in notified_patients:
            continue
        context = {
            'patient_name': patient.full_name,
            'amount': f'{bill.balance_due:.0f}',
            'bill_number': bill.bill_number,
        }
        body = render_template_body(template.body, context)
        send_notification(
            channel=template.channel,
            recipient=patient.phone,
            message=body,
            patient_id=patient.id,
            org_id=org_id,
            event_type='bill_due',
            template_id=template.id,
        )
        notified_patients.add(patient.id)
        sent += 1

    flash(f'{sent} bill reminder(s) sent.', 'success')
    return redirect(url_for('notifications.index'))


# ── Notification Logs ─────────────────────────────────────────────────────────

@notifications_bp.route('/logs')
@login_required
def logs():
    org_id = get_org_id()
    page = request.args.get('page', 1, type=int)
    channel = request.args.get('channel', 'all')
    event_type = request.args.get('event_type', 'all')

    query = NotificationLog.query.filter_by(org_id=org_id)
    if channel != 'all':
        query = query.filter_by(channel=channel)
    if event_type != 'all':
        query = query.filter_by(event_type=event_type)

    logs = query.order_by(NotificationLog.sent_at.desc()).paginate(page=page, per_page=50)
    return render_template('notifications/logs.html', logs=logs,
                           channel=channel, event_type=event_type)


# ── Scheduled Reminders Management ───────────────────────────────────────────

@notifications_bp.route('/scheduled')
@login_required
def scheduled():
    org_id = get_org_id()
    reminders = ScheduledReminder.query.filter_by(org_id=org_id).order_by(
        ScheduledReminder.scheduled_at
    ).limit(100).all()
    return render_template('notifications/scheduled.html', reminders=reminders)


@notifications_bp.route('/scheduled/<int:rid>/cancel', methods=['POST'])
@login_required
def cancel_reminder(rid):
    org_id = get_org_id()
    reminder = ScheduledReminder.query.filter_by(id=rid, org_id=org_id).first_or_404()
    reminder.status = 'cancelled'
    db.session.commit()
    return jsonify({'success': True})


# ── Stats API ─────────────────────────────────────────────────────────────────

@notifications_bp.route('/stats')
@login_required
def stats():
    org_id = get_org_id()
    today = date.today()
    week_ago = datetime.utcnow() - timedelta(days=7)

    total_sent = NotificationLog.query.filter_by(org_id=org_id, status='sent').count()
    failed = NotificationLog.query.filter_by(org_id=org_id, status='failed').count()
    this_week = NotificationLog.query.filter(
        NotificationLog.org_id == org_id,
        NotificationLog.sent_at >= week_ago,
    ).count()

    by_channel = {}
    for ch in ['sms', 'whatsapp', 'email']:
        by_channel[ch] = NotificationLog.query.filter_by(org_id=org_id, channel=ch).count()

    by_event = {}
    for evt in ['appointment_reminder', 'follow_up_due', 'bill_due', 'manual']:
        by_event[evt] = NotificationLog.query.filter_by(org_id=org_id, event_type=evt).count()

    return jsonify({
        'total_sent': total_sent,
        'failed': failed,
        'this_week': this_week,
        'by_channel': by_channel,
        'by_event': by_event,
    })
