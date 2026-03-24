"""
Tenant Onboarding Wizard — step-by-step setup for new organizations.
10 minutes to go live.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import (db, Organization, Branch, Doctor, Department, Staff, User,
                    OnboardingProgress, ServiceCatalog, DoctorSchedule, SystemSetting,
                    NotificationTemplate)
from datetime import datetime
import re

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/onboarding')

STEPS = [
    {'key': 'org_profile',  'label': 'Organization Profile', 'icon': 'building'},
    {'key': 'branch',       'label': 'Main Branch Setup',    'icon': 'map-marker-alt'},
    {'key': 'departments',  'label': 'Departments',           'icon': 'sitemap'},
    {'key': 'doctors',      'label': 'Add Doctors',           'icon': 'user-md'},
    {'key': 'services',     'label': 'Services & Pricing',    'icon': 'list-alt'},
    {'key': 'schedule',     'label': 'Doctor Schedules',      'icon': 'calendar-alt'},
    {'key': 'staff',        'label': 'Invite Staff',          'icon': 'users'},
    {'key': 'reminders',    'label': 'Reminders & AI',        'icon': 'bell'},
]


def get_or_create_progress(org_id):
    progress = OnboardingProgress.query.filter_by(org_id=org_id).first()
    if not progress:
        progress = OnboardingProgress(org_id=org_id)
        db.session.add(progress)
        db.session.commit()
    return progress


def get_org():
    if not current_user.org_id:
        return None
    return Organization.query.get(current_user.org_id)


# ── Entry point ───────────────────────────────────────────────────────────────

@onboarding_bp.route('/')
@login_required
def index():
    org = get_org()
    if not org:
        flash('No organization found. Please register first.', 'danger')
        return redirect(url_for('auth.register'))

    progress = get_or_create_progress(org.id)
    if progress.is_complete:
        return redirect(url_for('main.dashboard'))

    return render_template('onboarding/index.html',
        org=org, progress=progress, steps=STEPS)


# ── Step 1: Organization Profile ─────────────────────────────────────────────

@onboarding_bp.route('/org-profile', methods=['GET', 'POST'])
@login_required
def org_profile():
    org = get_org()
    if not org:
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        org.name = request.form.get('name', org.name).strip()
        org.address = request.form.get('address', org.address)
        org.contact_phone = request.form.get('contact_phone', org.contact_phone)
        org.country = request.form.get('country', org.country)
        org.currency = request.form.get('currency', org.currency)
        db.session.commit()

        progress = get_or_create_progress(org.id)
        progress.step_org_profile = True
        db.session.commit()

        flash('Organization profile saved!', 'success')
        return redirect(url_for('onboarding.setup_branch'))

    progress = get_or_create_progress(org.id)
    return render_template('onboarding/org_profile.html',
        org=org, progress=progress, steps=STEPS, current_step='org_profile')


# ── Step 2: Branch Setup ─────────────────────────────────────────────────────

@onboarding_bp.route('/branch', methods=['GET', 'POST'])
@login_required
def setup_branch():
    org = get_org()
    if not org:
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        branch = Branch.query.filter_by(org_id=org.id, is_main=True).first()
        if not branch:
            branch = Branch(org_id=org.id, is_main=True)
            db.session.add(branch)

        branch.name = request.form.get('branch_name', '').strip() or org.name + ' - Main'
        branch.address = request.form.get('address', org.address)
        branch.city = request.form.get('city', '')
        branch.phone = request.form.get('phone', org.contact_phone)
        branch.email = request.form.get('email', org.contact_email)
        branch.opening_time = request.form.get('opening_time', '09:00')
        branch.closing_time = request.form.get('closing_time', '18:00')
        branch.working_days = ','.join(request.form.getlist('working_days') or
                                        ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'])
        db.session.commit()

        progress = get_or_create_progress(org.id)
        progress.step_branch = True
        db.session.commit()

        flash('Branch configured!', 'success')
        return redirect(url_for('onboarding.setup_doctors'))

    branch = Branch.query.filter_by(org_id=org.id, is_main=True).first()
    progress = get_or_create_progress(org.id)
    return render_template('onboarding/branch.html',
        org=org, branch=branch, progress=progress, steps=STEPS, current_step='branch')


# ── Step 3: Add Doctors ───────────────────────────────────────────────────────

@onboarding_bp.route('/doctors', methods=['GET', 'POST'])
@login_required
def setup_doctors():
    org = get_org()
    if not org:
        return redirect(url_for('auth.register'))

    branch = Branch.query.filter_by(org_id=org.id, is_main=True).first()

    if request.method == 'POST':
        first_names = request.form.getlist('first_name')
        last_names = request.form.getlist('last_name')
        specializations = request.form.getlist('specialization')
        phones = request.form.getlist('phone')
        fees = request.form.getlist('consultation_fee')

        added = 0
        for i, fname in enumerate(first_names):
            if not fname.strip():
                continue
            # Create a placeholder user for this doctor
            username = re.sub(r'[^a-z0-9]', '', (fname + last_names[i]).lower()) + str(i + 1)
            if User.query.filter_by(username=username).first():
                username += '_doc'
            placeholder_user = User(
                username=username,
                email=f'{username}@{org.slug}.medios',
                role='doctor',
                org_id=org.id,
            )
            placeholder_user.set_password('changeme123')
            db.session.add(placeholder_user)
            db.session.flush()

            doc = Doctor(
                org_id=org.id,
                branch_id=branch.id if branch else None,
                user_id=placeholder_user.id,
                first_name=fname.strip(),
                last_name=last_names[i].strip() if i < len(last_names) else '',
                specialization=specializations[i].strip() if i < len(specializations) else 'General',
                phone=phones[i].strip() if i < len(phones) else '',
                consultation_fee=float(fees[i]) if i < len(fees) and fees[i] else 0.0,
            )
            db.session.add(doc)
            added += 1

        db.session.commit()

        progress = get_or_create_progress(org.id)
        progress.step_doctors = True
        db.session.commit()

        flash(f'{added} doctor(s) added!', 'success')
        return redirect(url_for('onboarding.setup_services'))

    doctors = Doctor.query.filter_by(org_id=org.id).all()
    progress = get_or_create_progress(org.id)
    return render_template('onboarding/doctors.html',
        org=org, doctors=doctors, progress=progress, steps=STEPS, current_step='doctors')


# ── Step 4: Services & Pricing ────────────────────────────────────────────────

@onboarding_bp.route('/services', methods=['GET', 'POST'])
@login_required
def setup_services():
    org = get_org()
    if not org:
        return redirect(url_for('auth.register'))

    branch = Branch.query.filter_by(org_id=org.id, is_main=True).first()

    if request.method == 'POST':
        names = request.form.getlist('service_name')
        categories = request.form.getlist('category')
        prices = request.form.getlist('price')
        durations = request.form.getlist('duration')

        for i, name in enumerate(names):
            if not name.strip():
                continue
            svc = ServiceCatalog(
                org_id=org.id,
                branch_id=branch.id if branch else None,
                name=name.strip(),
                category=categories[i] if i < len(categories) else 'consultation',
                price=float(prices[i]) if i < len(prices) and prices[i] else 0.0,
                duration_minutes=int(durations[i]) if i < len(durations) and durations[i] else 30,
            )
            db.session.add(svc)

        db.session.commit()

        progress = get_or_create_progress(org.id)
        progress.step_services = True
        db.session.commit()

        flash('Services configured!', 'success')
        return redirect(url_for('onboarding.setup_schedule'))

    services = ServiceCatalog.query.filter_by(org_id=org.id).all()
    progress = get_or_create_progress(org.id)
    return render_template('onboarding/services.html',
        org=org, services=services, progress=progress, steps=STEPS, current_step='services')


# ── Step 5: Doctor Schedules ──────────────────────────────────────────────────

@onboarding_bp.route('/schedule', methods=['GET', 'POST'])
@login_required
def setup_schedule():
    org = get_org()
    if not org:
        return redirect(url_for('auth.register'))

    branch = Branch.query.filter_by(org_id=org.id, is_main=True).first()
    doctors = Doctor.query.filter_by(org_id=org.id).all()

    if request.method == 'POST':
        doctor_ids = request.form.getlist('doctor_id')
        days_list = request.form.getlist('days')
        start_times = request.form.getlist('start_time')
        end_times = request.form.getlist('end_time')
        slot_durations = request.form.getlist('slot_duration')

        for i, doc_id in enumerate(doctor_ids):
            if not doc_id:
                continue
            days = days_list[i].split(',') if i < len(days_list) else ['Mon']
            for day in days:
                sched = DoctorSchedule(
                    org_id=org.id,
                    branch_id=branch.id if branch else None,
                    doctor_id=int(doc_id),
                    day_of_week=day.strip(),
                    start_time=start_times[i] if i < len(start_times) else '09:00',
                    end_time=end_times[i] if i < len(end_times) else '17:00',
                    slot_duration=int(slot_durations[i]) if i < len(slot_durations) and slot_durations[i] else 15,
                )
                db.session.add(sched)

        db.session.commit()

        progress = get_or_create_progress(org.id)
        progress.step_schedule = True
        db.session.commit()

        flash('Schedules saved!', 'success')
        return redirect(url_for('onboarding.setup_staff'))

    progress = get_or_create_progress(org.id)
    return render_template('onboarding/schedule.html',
        org=org, doctors=doctors, progress=progress, steps=STEPS, current_step='schedule')


# ── Step 6: Invite Staff ──────────────────────────────────────────────────────

@onboarding_bp.route('/staff', methods=['GET', 'POST'])
@login_required
def setup_staff():
    org = get_org()
    if not org:
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        names = request.form.getlist('full_name')
        emails = request.form.getlist('email')
        roles = request.form.getlist('role')

        invited = 0
        for i, name in enumerate(names):
            if not name.strip() or i >= len(emails) or not emails[i].strip():
                continue
            email = emails[i].strip().lower()
            if User.query.filter_by(email=email).first():
                continue
            username = re.sub(r'[^a-z0-9]', '', email.split('@')[0]) + str(i)
            role = roles[i] if i < len(roles) else 'receptionist'
            user = User(
                username=username,
                email=email,
                role=role,
                org_id=org.id,
            )
            user.set_password('changeme123')
            db.session.add(user)
            invited += 1

        db.session.commit()

        progress = get_or_create_progress(org.id)
        progress.step_staff = True
        db.session.commit()

        flash(f'{invited} staff member(s) invited!', 'success')
        return redirect(url_for('onboarding.setup_reminders'))

    progress = get_or_create_progress(org.id)
    staff_users = User.query.filter(
        User.org_id == org.id,
        User.role.in_(['receptionist', 'nurse', 'pharmacist', 'lab_tech'])
    ).all()
    return render_template('onboarding/staff.html',
        org=org, staff_users=staff_users, progress=progress, steps=STEPS, current_step='staff')


# ── Step 7: Reminders & AI ────────────────────────────────────────────────────

@onboarding_bp.route('/reminders', methods=['GET', 'POST'])
@login_required
def setup_reminders():
    org = get_org()
    if not org:
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        enable_reminders = request.form.get('enable_reminders') == 'on'
        enable_ai = request.form.get('enable_ai') == 'on'

        if enable_reminders:
            # Create default notification templates
            defaults = [
                {
                    'name': 'Appointment Reminder',
                    'event_type': 'appointment_reminder',
                    'channel': 'sms',
                    'body': 'Dear {{patient_name}}, your appointment with {{doctor_name}} is tomorrow at {{appointment_time}}. Please arrive 10 minutes early.',
                    'send_before_hours': 24,
                },
                {
                    'name': 'Follow-up Due',
                    'event_type': 'follow_up_due',
                    'channel': 'sms',
                    'body': 'Dear {{patient_name}}, your follow-up visit is due. Please book an appointment with {{doctor_name}}.',
                    'send_before_hours': 0,
                },
                {
                    'name': 'Bill Due Reminder',
                    'event_type': 'bill_due',
                    'channel': 'sms',
                    'body': 'Dear {{patient_name}}, you have an outstanding bill of {{amount}}. Please clear it at your earliest convenience.',
                    'send_before_hours': 0,
                },
            ]
            for tmpl_data in defaults:
                exists = NotificationTemplate.query.filter_by(
                    org_id=org.id, event_type=tmpl_data['event_type']
                ).first()
                if not exists:
                    tmpl = NotificationTemplate(org_id=org.id, **tmpl_data)
                    db.session.add(tmpl)

        db.session.commit()

        progress = get_or_create_progress(org.id)
        progress.step_reminders = True
        progress.is_complete = True
        progress.completed_at = datetime.utcnow()
        db.session.commit()

        flash('Setup complete! Welcome to MediOS!', 'success')
        return redirect(url_for('onboarding.complete'))

    progress = get_or_create_progress(org.id)
    templates = NotificationTemplate.query.filter_by(org_id=org.id).all()
    return render_template('onboarding/reminders.html',
        org=org, templates=templates, progress=progress, steps=STEPS, current_step='reminders')


# ── Completion ────────────────────────────────────────────────────────────────

@onboarding_bp.route('/complete')
@login_required
def complete():
    org = get_org()
    progress = get_or_create_progress(org.id) if org else None
    return render_template('onboarding/complete.html', org=org, progress=progress)


# ── AJAX: check completion status ─────────────────────────────────────────────

@onboarding_bp.route('/status')
@login_required
def status():
    org = get_org()
    if not org:
        return jsonify({'error': 'No org'})
    progress = get_or_create_progress(org.id)
    return jsonify({
        'completion_pct': progress.completion_pct,
        'is_complete': progress.is_complete,
        'steps': {
            'org_profile': progress.step_org_profile,
            'branch': progress.step_branch,
            'doctors': progress.step_doctors,
            'services': progress.step_services,
            'schedule': progress.step_schedule,
            'billing': progress.step_billing,
            'staff': progress.step_staff,
            'reminders': progress.step_reminders,
        }
    })
