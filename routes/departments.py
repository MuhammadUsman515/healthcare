from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from models import db, Department, Doctor

departments_bp = Blueprint('departments', __name__, url_prefix='/departments')


@departments_bp.route('/')
@login_required
def index():
    departments = Department.query.all()
    return render_template('departments/index.html', departments=departments)


@departments_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        dept = Department(
            name=request.form.get('name'),
            description=request.form.get('description'),
        )
        db.session.add(dept)
        db.session.commit()
        flash(f'Department {dept.name} created!', 'success')
        return redirect(url_for('departments.index'))
    return render_template('departments/new.html')


@departments_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    dept = Department.query.get_or_404(id)
    doctors = Doctor.query.filter_by(department_id=id, status='active').all()

    if request.method == 'POST':
        dept.name = request.form.get('name')
        dept.description = request.form.get('description')
        head_id = request.form.get('head_doctor_id')
        dept.head_doctor_id = int(head_id) if head_id else None
        db.session.commit()
        flash(f'Department {dept.name} updated!', 'success')
        return redirect(url_for('departments.index'))

    return render_template('departments/edit.html', dept=dept, doctors=doctors)
