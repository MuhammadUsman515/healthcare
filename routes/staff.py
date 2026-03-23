from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Staff, User, Department
from datetime import datetime
import random
import string

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')


def generate_employee_id():
    return 'EMP' + ''.join(random.choices(string.digits, k=5))


@staff_bp.route('/')
@login_required
def index():
    search = request.args.get('search', '')
    role_filter = request.args.get('role', 'all')
    dept_filter = request.args.get('department', 'all')

    query = Staff.query
    if search:
        query = query.filter(
            (Staff.first_name.ilike(f'%{search}%')) |
            (Staff.last_name.ilike(f'%{search}%')) |
            (Staff.employee_id.ilike(f'%{search}%')) |
            (Staff.phone.ilike(f'%{search}%'))
        )
    if role_filter != 'all':
        query = query.filter_by(role=role_filter)
    if dept_filter != 'all':
        query = query.filter_by(department_id=int(dept_filter))

    staff = query.order_by(Staff.first_name).all()
    departments = Department.query.all()
    return render_template('staff/index.html', staff=staff, departments=departments,
                           search=search, role_filter=role_filter, dept_filter=dept_filter)


@staff_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    departments = Department.query.all()
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('staff/new.html', departments=departments)

        user = User(username=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        join_date_str = request.form.get('join_date')
        join_date = datetime.strptime(join_date_str, '%Y-%m-%d').date() if join_date_str else None

        staff = Staff(
            user_id=user.id,
            employee_id=generate_employee_id(),
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            role=role,
            department_id=request.form.get('department_id') or None,
            phone=request.form.get('phone'),
            email=email,
            join_date=join_date,
            shift=request.form.get('shift'),
            salary=float(request.form.get('salary', 0) or 0),
            address=request.form.get('address'),
            emergency_contact=request.form.get('emergency_contact'),
            qualification=request.form.get('qualification'),
        )
        db.session.add(staff)
        db.session.commit()
        flash(f'Staff member {staff.first_name} {staff.last_name} added. ID: {staff.employee_id}', 'success')
        return redirect(url_for('staff.view', id=staff.id))

    return render_template('staff/new.html', departments=departments)


@staff_bp.route('/<int:id>')
@login_required
def view(id):
    member = Staff.query.get_or_404(id)
    return render_template('staff/view.html', member=member)


@staff_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    member = Staff.query.get_or_404(id)
    departments = Department.query.all()
    if request.method == 'POST':
        join_date_str = request.form.get('join_date')
        member.first_name = request.form.get('first_name')
        member.last_name = request.form.get('last_name')
        member.role = request.form.get('role')
        member.department_id = request.form.get('department_id') or None
        member.phone = request.form.get('phone')
        member.email = request.form.get('email')
        member.join_date = datetime.strptime(join_date_str, '%Y-%m-%d').date() if join_date_str else member.join_date
        member.shift = request.form.get('shift')
        member.salary = float(request.form.get('salary', 0) or 0)
        member.address = request.form.get('address')
        member.emergency_contact = request.form.get('emergency_contact')
        member.qualification = request.form.get('qualification')
        member.status = request.form.get('status', 'active')
        db.session.commit()
        flash('Staff information updated successfully!', 'success')
        return redirect(url_for('staff.view', id=member.id))
    return render_template('staff/edit.html', member=member, departments=departments)


@staff_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    member = Staff.query.get_or_404(id)
    member.status = 'inactive'
    db.session.commit()
    flash(f'{member.first_name} {member.last_name} has been deactivated.', 'info')
    return redirect(url_for('staff.index'))
