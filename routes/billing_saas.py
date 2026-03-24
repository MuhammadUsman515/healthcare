"""
SaaS Billing & Usage Metering
- Subscription management
- Plan enforcement (feature gates)
- Usage tracking per tenant
- Payment gateway hook (Stripe-ready)
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from models import (db, Organization, User, Patient, Appointment, Bill,
                    TenantUsageMetric, AIUsageLog, NotificationLog,
                    Branch, PLAN_FEATURES, PLAN_PRICING)
from datetime import datetime, date, timedelta
from sqlalchemy import func

billing_saas_bp = Blueprint('billing_saas', __name__, url_prefix='/saas/billing')

# ── Plan Pricing (monthly, USD equivalent) ───────────────────────────────────
PLAN_MONTHLY_USD = {
    'basic':      2,
    'standard':   5,
    'pro':        12,
    'enterprise': 30,
}

PLAN_MONTHLY_PKR = {
    'basic':      450,
    'standard':   1200,
    'pro':        3500,
    'enterprise': 9000,
}


# ── Feature gate decorator ────────────────────────────────────────────────────

def feature_required(feature_key):
    """Decorator: blocks route if org's plan doesn't include the feature."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if current_user.org_id:
                org = Organization.query.get(current_user.org_id)
                if org and not org.has_feature(feature_key):
                    plan_features = PLAN_FEATURES.get(org.plan_type, {})
                    return render_template('saas/feature_locked.html',
                        feature=feature_key, org=org,
                        plan_features=plan_features,
                        plan_monthly_pkr=PLAN_MONTHLY_PKR)
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Subscription Dashboard ────────────────────────────────────────────────────

@billing_saas_bp.route('/')
@login_required
def dashboard():
    org = None
    if current_user.org_id:
        org = Organization.query.get(current_user.org_id)

    if not org:
        flash('No organization found.', 'danger')
        return redirect(url_for('main.dashboard'))

    plan_features = org.get_plan_features()
    usage = _get_current_usage(org.id)
    usage_history = TenantUsageMetric.query.filter_by(org_id=org.id).order_by(
        TenantUsageMetric.month.desc()
    ).limit(6).all()

    # Available plans for upgrade
    plans = []
    for plan_key, features in PLAN_FEATURES.items():
        plans.append({
            'key': plan_key,
            'label': features['label'],
            'price_pkr': PLAN_MONTHLY_PKR.get(plan_key, 0),
            'price_usd': PLAN_MONTHLY_USD.get(plan_key, 0),
            'features': features,
            'is_current': org.plan_type == plan_key,
        })

    return render_template('saas/billing_dashboard.html',
        org=org, plan_features=plan_features, usage=usage,
        usage_history=usage_history, plans=plans,
        plan_monthly_pkr=PLAN_MONTHLY_PKR, plan_monthly_usd=PLAN_MONTHLY_USD)


# ── Upgrade Plan ──────────────────────────────────────────────────────────────

@billing_saas_bp.route('/upgrade', methods=['GET', 'POST'])
@login_required
def upgrade():
    org = Organization.query.get(current_user.org_id) if current_user.org_id else None
    if not org:
        flash('No organization found.', 'danger')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        new_plan = request.form.get('plan_type')
        payment_method = request.form.get('payment_method', 'manual')
        billing_cycle = request.form.get('billing_cycle', 'monthly')

        if new_plan not in PLAN_FEATURES:
            flash('Invalid plan.', 'danger')
            return redirect(url_for('billing_saas.upgrade'))

        # TODO: Stripe integration
        # For now, simulate payment success
        if payment_method == 'stripe':
            # stripe.PaymentIntent.create(...)
            pass

        old_plan = org.plan_type
        org.plan_type = new_plan
        org.subscription_status = 'active'
        # Update limits from plan
        org.max_users = PLAN_FEATURES[new_plan]['max_users']
        db.session.commit()

        flash(f'Plan upgraded from {old_plan} to {new_plan}!', 'success')
        _snapshot_usage(org.id)
        return redirect(url_for('billing_saas.dashboard'))

    plans = [
        {
            'key': k,
            'label': v['label'],
            'price_pkr': PLAN_MONTHLY_PKR.get(k, 0),
            'price_usd': PLAN_MONTHLY_USD.get(k, 0),
            'features': v,
            'is_current': org.plan_type == k,
        }
        for k, v in PLAN_FEATURES.items()
    ]
    return render_template('saas/upgrade.html', org=org, plans=plans)


# ── Usage Metering ────────────────────────────────────────────────────────────

def _get_current_usage(org_id):
    month = date.today().strftime('%Y-%m')
    month_start = date.today().replace(day=1)

    return {
        'month': month,
        'active_users': User.query.filter_by(org_id=org_id, is_active=True).count(),
        'active_branches': Branch.query.filter_by(org_id=org_id, is_active=True).count(),
        'patients_this_month': Patient.query.filter(
            Patient.org_id == org_id,
            Patient.created_at >= month_start
        ).count(),
        'appointments_this_month': Appointment.query.filter(
            Appointment.org_id == org_id,
            Appointment.appointment_date >= month_start
        ).count(),
        'ai_calls_this_month': AIUsageLog.query.filter(
            AIUsageLog.org_id == org_id,
            AIUsageLog.created_at >= month_start
        ).count(),
        'reminders_this_month': NotificationLog.query.filter(
            NotificationLog.org_id == org_id,
            NotificationLog.sent_at >= month_start
        ).count(),
        'bills_this_month': Bill.query.filter(
            Bill.org_id == org_id,
            Bill.bill_date >= month_start
        ).count(),
    }


def _snapshot_usage(org_id):
    """Save a usage snapshot for the current month."""
    month = date.today().strftime('%Y-%m')
    usage = _get_current_usage(org_id)

    metric = TenantUsageMetric.query.filter_by(org_id=org_id, month=month).first()
    if not metric:
        metric = TenantUsageMetric(org_id=org_id, month=month)
        db.session.add(metric)

    metric.active_users = usage['active_users']
    metric.active_branches = usage['active_branches']
    metric.patients_registered = usage['patients_this_month']
    metric.appointments_booked = usage['appointments_this_month']
    metric.ai_calls = usage['ai_calls_this_month']
    metric.reminders_sent = usage['reminders_this_month']
    metric.bills_generated = usage['bills_this_month']
    db.session.commit()
    return metric


@billing_saas_bp.route('/snapshot-usage', methods=['POST'])
@login_required
def snapshot_usage():
    if not current_user.org_id:
        return jsonify({'error': 'No org'}), 400
    metric = _snapshot_usage(current_user.org_id)
    return jsonify({
        'month': metric.month,
        'active_users': metric.active_users,
        'patients_registered': metric.patients_registered,
        'ai_calls': metric.ai_calls,
    })


@billing_saas_bp.route('/usage')
@login_required
def usage_report():
    org = Organization.query.get(current_user.org_id) if current_user.org_id else None
    if not org:
        return redirect(url_for('main.dashboard'))

    usage = _get_current_usage(org.id)
    plan_features = org.get_plan_features()
    history = TenantUsageMetric.query.filter_by(org_id=org.id).order_by(
        TenantUsageMetric.month.desc()
    ).limit(12).all()

    # Check limits
    limits = {
        'users': {
            'used': usage['active_users'],
            'max': plan_features['max_users'],
            'pct': int(usage['active_users'] / max(plan_features['max_users'], 1) * 100),
        },
        'branches': {
            'used': usage['active_branches'],
            'max': plan_features['max_branches'],
            'pct': int(usage['active_branches'] / max(plan_features['max_branches'], 1) * 100),
        },
        'patients': {
            'used': usage['patients_this_month'],
            'max': plan_features['max_patients_per_month'],
            'pct': int(usage['patients_this_month'] / max(plan_features['max_patients_per_month'], 1) * 100),
        },
    }

    return render_template('saas/usage_report.html',
        org=org, usage=usage, limits=limits, history=history, plan_features=plan_features)


# ── Plan Enforcement Check ────────────────────────────────────────────────────

@billing_saas_bp.route('/check-limits')
@login_required
def check_limits():
    """API: check if org is within plan limits."""
    if not current_user.org_id:
        return jsonify({'ok': True})

    org = Organization.query.get(current_user.org_id)
    if not org:
        return jsonify({'ok': True})

    warnings = []
    plan_features = org.get_plan_features()
    usage = _get_current_usage(org.id)

    if usage['active_users'] >= plan_features['max_users']:
        warnings.append(f"User limit reached ({plan_features['max_users']}). Upgrade plan.")

    if usage['active_branches'] >= plan_features['max_branches']:
        warnings.append(f"Branch limit reached ({plan_features['max_branches']}). Upgrade plan.")

    if usage['patients_this_month'] >= plan_features['max_patients_per_month'] * 0.9:
        warnings.append(f"Approaching monthly patient limit ({plan_features['max_patients_per_month']}).")

    return jsonify({
        'ok': len(warnings) == 0,
        'warnings': warnings,
        'usage': usage,
        'plan': org.plan_type,
        'limits': plan_features,
    })


# ── Stripe Webhook (placeholder) ─────────────────────────────────────────────

@billing_saas_bp.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """
    Stripe webhook endpoint.
    TODO: Add stripe.Webhook.construct_event() verification.
    """
    payload = request.get_json(force=True) or {}
    event_type = payload.get('type')

    if event_type == 'payment_intent.succeeded':
        # Find org by metadata and activate
        metadata = payload.get('data', {}).get('object', {}).get('metadata', {})
        org_id = metadata.get('org_id')
        plan = metadata.get('plan')
        if org_id and plan:
            org = Organization.query.get(int(org_id))
            if org:
                org.subscription_status = 'active'
                org.plan_type = plan
                db.session.commit()

    elif event_type == 'customer.subscription.deleted':
        metadata = payload.get('data', {}).get('object', {}).get('metadata', {})
        org_id = metadata.get('org_id')
        if org_id:
            org = Organization.query.get(int(org_id))
            if org:
                org.subscription_status = 'expired'
                db.session.commit()

    return jsonify({'received': True})
