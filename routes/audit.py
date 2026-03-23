from flask import Blueprint, render_template, request
from flask_login import login_required
from models import AuditLog, User

audit_bp = Blueprint('audit', __name__, url_prefix='/audit')


@audit_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    resource = request.args.get('resource', 'all')
    user_filter = request.args.get('user', 'all')
    status = request.args.get('status', 'all')

    query = AuditLog.query
    if resource != 'all':
        query = query.filter_by(resource_type=resource)
    if user_filter != 'all':
        query = query.filter_by(user_id=int(user_filter))
    if status != 'all':
        query = query.filter_by(status=status)

    logs = query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    users = User.query.order_by(User.username).all()
    resource_types = db.session.query(AuditLog.resource_type).distinct().all() if False else []

    return render_template('audit/index.html', logs=logs, users=users,
                           resource=resource, user_filter=user_filter, status=status)


# Import db for the query above
from models import db
