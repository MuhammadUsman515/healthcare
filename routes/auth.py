from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import re
from models import db, User, Organization

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password) and user.is_active:
            # Check org subscription
            if user.org_id:
                org = Organization.query.get(user.org_id)
                if org and not org.is_active:
                    flash('Your subscription has expired. Please contact your administrator.', 'danger')
                    return render_template('auth/login.html')

            login_user(user)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(next_page or url_for('main.dashboard'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        org_name     = request.form.get('org_name', '').strip()
        plan_type    = request.form.get('plan_type', 'clinic')
        country      = request.form.get('country', 'Pakistan')
        currency     = request.form.get('currency', 'PKR')
        contact_email = request.form.get('email', '').strip().lower()
        contact_phone = request.form.get('phone', '').strip()
        username     = request.form.get('username', '').strip()
        password     = request.form.get('password', '')
        confirm_pw   = request.form.get('confirm_password', '')

        # Validations
        errors = []
        if not org_name:
            errors.append('Organization name is required.')
        if not contact_email or not re.match(r'^[^@]+@[^@]+\.[^@]+$', contact_email):
            errors.append('Valid email is required.')
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != confirm_pw:
            errors.append('Passwords do not match.')
        if User.query.filter_by(username=username).first():
            errors.append('Username already taken.')
        if User.query.filter_by(email=contact_email).first():
            errors.append('Email already registered.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('auth/register.html', form_data=request.form)

        # Create slug
        slug = re.sub(r'[^a-z0-9]', '-', org_name.lower())
        slug = re.sub(r'-+', '-', slug).strip('-')
        # Ensure unique slug
        base_slug = slug
        counter = 1
        while Organization.query.filter_by(slug=slug).first():
            slug = f'{base_slug}-{counter}'
            counter += 1

        # Create org with 15-day trial
        now = datetime.utcnow()
        org = Organization(
            name=org_name,
            slug=slug,
            plan_type=plan_type,
            country=country,
            currency=currency,
            contact_email=contact_email,
            contact_phone=contact_phone,
            trial_start=now,
            trial_end=now + timedelta(days=15),
            subscription_status='trial',
            max_users=5,
        )
        db.session.add(org)
        db.session.flush()  # get org.id

        # Create admin user
        user = User(
            username=username,
            email=contact_email,
            role='admin',
            is_active=True,
            org_id=org.id,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(f'Welcome to BizVinc! Your 15-day free trial has started.', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('auth/register.html', form_data={})


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
