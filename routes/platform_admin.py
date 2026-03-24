"""
Platform Admin — MediOS internal super-admin panel.
Only accessible to users with role='superadmin'.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from models import (db, Organization, User, Patient, Appointment, Bill,
                    AIInsight, TenantUsageMetric, PlatformAlert, NotificationLog,
                    AIUsageLog, FollowUpTask, Branch, OnboardingProgress, PLAN_FEATURES)
from datetime import datetime, date, timedelta
from sqlalchemy import func

platform_admin_bp = Blueprint('platform_admin', __name__, url_prefix='/platform-admin')


def superadmin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'superadmin':
            flash('Access denied. Super admin only.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ─────────────────────────────────────────────────────────────────

@platform_admin_bp.route('/')
@login_required
@superadmin_required
def dashboard():
    today = date.today()
    month_start = today.replace(day=1)

    # Tenant stats
    total_tenants = Organization.query.count()
    active_tenants = Organization.query.filter_by(subscription_status='active').count()
    trial_tenants = Organization.query.filter_by(subscription_status='trial').count()
    expired_tenants = Organization.query.filter_by(subscription_status='expired').count()

    # Trials expiring in next 3 days
    expiring_soon = Organization.query.filter(
        Organization.subscription_status == 'trial',
        Organization.trial_end <= datetime.utcnow() + timedelta(days=3),
        Organization.trial_end >= datetime.utcnow()
    ).count()

    # MRR calculation (basic: active orgs × avg plan price in USD)
    plan_usd = {'basic': 2, 'standard': 5, 'pro': 12, 'enterprise': 30}
    active_orgs = Organization.query.filter_by(subscription_status='active').all()
    mrr = sum(plan_usd.get(o.plan_type, 2) for o in active_orgs)

    # New tenants this month
    new_this_month = Organization.query.filter(
        Organization.created_at >= month_start
    ).count()

    # Platform alerts
    open_alerts = PlatformAlert.query.filter_by(is_resolved=False).order_by(
        PlatformAlert.created_at.desc()
    ).limit(10).all()

    # Recent tenants
    recent_tenants = Organization.query.order_by(Organization.created_at.desc()).limit(10).all()

    # Plan distribution
    plan_dist = {}
    for plan in ['basic', 'standard', 'pro', 'enterprise']:
        plan_dist[plan] = Organization.query.filter_by(plan_type=plan).count()

    # AI usage this month
    ai_calls_month = AIUsageLog.query.filter(
        AIUsageLog.created_at >= month_start
    ).count()

    # Total users across all tenants
    total_users = User.query.filter(User.org_id.isnot(None)).count()

    # Churn (expired this month)
    churn_month = Organization.query.filter(
        Organization.subscription_status == 'expired',
        Organization.created_at >= month_start
    ).count()

    return render_template('platform_admin/dashboard.html',
        total_tenants=total_tenants,
        active_tenants=active_tenants,
        trial_tenants=trial_tenants,
        expired_tenants=expired_tenants,
        expiring_soon=expiring_soon,
        mrr=mrr,
        new_this_month=new_this_month,
        open_alerts=open_alerts,
        recent_tenants=recent_tenants,
        plan_dist=plan_dist,
        ai_calls_month=ai_calls_month,
        total_users=total_users,
        churn_month=churn_month,
    )


@platform_admin_bp.route('/tenants')
@login_required
@superadmin_required
def tenants():
    search = request.args.get('search', '')
    status = request.args.get('status', 'all')
    plan = request.args.get('plan', 'all')

    query = Organization.query
    if search:
        query = query.filter(
            Organization.name.ilike(f'%{search}%') |
            Organization.contact_email.ilike(f'%{search}%')
        )
    if status != 'all':
        query = query.filter_by(subscription_status=status)
    if plan != 'all':
        query = query.filter_by(plan_type=plan)

    orgs = query.order_by(Organization.created_at.desc()).all()

    # Annotate with user count and patient count
    tenant_data = []
    for org in orgs:
        user_count = User.query.filter_by(org_id=org.id).count()
        patient_count = Patient.query.filter_by(org_id=org.id).count()
        onboarding = OnboardingProgress.query.filter_by(org_id=org.id).first()
        tenant_data.append({
            'org': org,
            'user_count': user_count,
            'patient_count': patient_count,
            'onboarding_pct': onboarding.completion_pct if onboarding else 0,
        })

    return render_template('platform_admin/tenants.html',
        tenant_data=tenant_data, search=search, status=status, plan=plan)


@platform_admin_bp.route('/tenants/<int:org_id>')
@login_required
@superadmin_required
def tenant_detail(org_id):
    org = Organization.query.get_or_404(org_id)
    users = User.query.filter_by(org_id=org_id).all()
    branches = Branch.query.filter_by(org_id=org_id).all()
    onboarding = OnboardingProgress.query.filter_by(org_id=org_id).first()

    # Usage stats
    patient_count = Patient.query.filter_by(org_id=org_id).count()
    appt_count = Appointment.query.filter_by(org_id=org_id).count()
    bill_count = Bill.query.filter_by(org_id=org_id).count()

    # AI usage
    ai_calls = AIUsageLog.query.filter_by(org_id=org_id).count()

    # Monthly usage history
    usage_history = TenantUsageMetric.query.filter_by(org_id=org_id).order_by(
        TenantUsageMetric.month.desc()
    ).limit(6).all()

    # AI insights for this tenant
    insights = AIInsight.query.filter_by(org_id=org_id).order_by(
        AIInsight.generated_at.desc()
    ).limit(5).all()

    plan_features = org.get_plan_features()

    return render_template('platform_admin/tenant_detail.html',
        org=org, users=users, branches=branches, onboarding=onboarding,
        patient_count=patient_count, appt_count=appt_count, bill_count=bill_count,
        ai_calls=ai_calls, usage_history=usage_history, insights=insights,
        plan_features=plan_features)


@platform_admin_bp.route('/tenants/<int:org_id>/change-plan', methods=['POST'])
@login_required
@superadmin_required
def change_tenant_plan(org_id):
    org = Organization.query.get_or_404(org_id)
    org.plan_type = request.form.get('plan_type', org.plan_type)
    org.subscription_status = request.form.get('subscription_status', org.subscription_status)
    db.session.commit()
    flash(f'Plan updated for {org.name}', 'success')
    return redirect(url_for('platform_admin.tenant_detail', org_id=org_id))


@platform_admin_bp.route('/tenants/<int:org_id>/extend-trial', methods=['POST'])
@login_required
@superadmin_required
def extend_trial(org_id):
    org = Organization.query.get_or_404(org_id)
    days = int(request.form.get('days', 7))
    if org.trial_end:
        org.trial_end = org.trial_end + timedelta(days=days)
    else:
        org.trial_end = datetime.utcnow() + timedelta(days=days)
    org.subscription_status = 'trial'
    db.session.commit()
    flash(f'Trial extended by {days} days for {org.name}', 'success')
    return redirect(url_for('platform_admin.tenant_detail', org_id=org_id))


@platform_admin_bp.route('/alerts')
@login_required
@superadmin_required
def alerts():
    alerts = PlatformAlert.query.order_by(
        PlatformAlert.is_resolved.asc(),
        PlatformAlert.created_at.desc()
    ).all()
    return render_template('platform_admin/alerts.html', alerts=alerts)


@platform_admin_bp.route('/alerts/<int:alert_id>/resolve', methods=['POST'])
@login_required
@superadmin_required
def resolve_alert(alert_id):
    alert = PlatformAlert.query.get_or_404(alert_id)
    alert.is_resolved = True
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by = current_user.id
    db.session.commit()
    return jsonify({'success': True})


@platform_admin_bp.route('/generate-alerts', methods=['POST'])
@login_required
@superadmin_required
def generate_platform_alerts():
    """Auto-detect and create platform alerts."""
    created = 0
    # Trials expiring in 2 days
    expiring = Organization.query.filter(
        Organization.subscription_status == 'trial',
        Organization.trial_end <= datetime.utcnow() + timedelta(days=2),
        Organization.trial_end >= datetime.utcnow()
    ).all()
    for org in expiring:
        existing = PlatformAlert.query.filter_by(
            org_id=org.id, alert_type='trial_expiring', is_resolved=False
        ).first()
        if not existing:
            alert = PlatformAlert(
                org_id=org.id,
                alert_type='trial_expiring',
                message=f'{org.name} trial expires in {org.trial_days_left} day(s). Follow up.',
                severity='warning',
            )
            db.session.add(alert)
            created += 1

    # Orgs with 0 patients (potential churn / onboarding failure)
    all_orgs = Organization.query.filter(
        Organization.subscription_status.in_(['trial', 'active'])
    ).all()
    for org in all_orgs:
        if Patient.query.filter_by(org_id=org.id).count() == 0:
            existing = PlatformAlert.query.filter_by(
                org_id=org.id, alert_type='no_activity', is_resolved=False
            ).first()
            if not existing:
                alert = PlatformAlert(
                    org_id=org.id,
                    alert_type='no_activity',
                    message=f'{org.name} has no patients yet. Onboarding may be stuck.',
                    severity='warning',
                )
                db.session.add(alert)
                created += 1

    db.session.commit()
    flash(f'{created} new platform alerts generated.', 'success')
    return redirect(url_for('platform_admin.alerts'))


@platform_admin_bp.route('/analytics')
@login_required
@superadmin_required
def analytics():
    """MRR, growth, churn, feature adoption."""
    plan_usd = {'basic': 2, 'standard': 5, 'pro': 12, 'enterprise': 30}

    # MRR by plan
    mrr_by_plan = {}
    for plan in ['basic', 'standard', 'pro', 'enterprise']:
        count = Organization.query.filter_by(
            plan_type=plan, subscription_status='active'
        ).count()
        mrr_by_plan[plan] = count * plan_usd[plan]

    total_mrr = sum(mrr_by_plan.values())
    arr = total_mrr * 12

    # Growth: new tenants per month (last 6 months)
    growth_labels = []
    growth_data = []
    today = date.today()
    for i in range(5, -1, -1):
        m = today.replace(day=1) - timedelta(days=i * 30)
        label = m.strftime('%b %Y')
        count = Organization.query.filter(
            func.strftime('%Y-%m', Organization.created_at) == m.strftime('%Y-%m')
        ).count()
        growth_labels.append(label)
        growth_data.append(count)

    # Feature adoption (which modules are most-used orgs on)
    plan_counts = {
        plan: Organization.query.filter_by(plan_type=plan).count()
        for plan in ['basic', 'standard', 'pro', 'enterprise']
    }

    # AI usage by feature
    ai_by_feature = db.session.query(
        AIUsageLog.feature, func.count(AIUsageLog.id)
    ).group_by(AIUsageLog.feature).all()

    return render_template('platform_admin/analytics.html',
        mrr_by_plan=mrr_by_plan, total_mrr=total_mrr, arr=arr,
        growth_labels=growth_labels, growth_data=growth_data,
        plan_counts=plan_counts, ai_by_feature=ai_by_feature)
