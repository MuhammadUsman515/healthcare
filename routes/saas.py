from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, Organization, PLAN_PRICING

saas_bp = Blueprint('saas', __name__, url_prefix='/saas')


@saas_bp.route('/pricing')
def pricing():
    return render_template('saas/pricing.html', pricing=PLAN_PRICING)


@saas_bp.route('/subscription')
@login_required
def subscription():
    org = None
    if current_user.org_id:
        org = Organization.query.get(current_user.org_id)
    return render_template('saas/subscription.html', org=org, pricing=PLAN_PRICING)


@saas_bp.route('/upgrade', methods=['POST'])
@login_required
def upgrade():
    if not current_user.org_id:
        flash('No organization found.', 'danger')
        return redirect(url_for('saas.subscription'))

    org = Organization.query.get(current_user.org_id)
    plan_type = request.form.get('plan_type', org.plan_type)
    currency = request.form.get('currency', org.currency)
    max_users = int(request.form.get('max_users', org.max_users))

    org.plan_type = plan_type
    org.currency = currency
    org.max_users = max_users
    org.subscription_status = 'active'
    db.session.commit()

    flash('Subscription upgraded successfully!', 'success')
    return redirect(url_for('saas.subscription'))
