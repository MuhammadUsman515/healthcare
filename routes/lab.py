from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from models import db, LabTestCatalog, LabTest, MedicalRecord, Patient, Doctor
from datetime import datetime, date

lab_bp = Blueprint('lab', __name__, url_prefix='/lab')


@lab_bp.route('/')
@login_required
def index():
    pending = LabTest.query.filter_by(status='pending').order_by(LabTest.test_date.desc()).all()
    recent_completed = LabTest.query.filter_by(status='completed').order_by(LabTest.test_date.desc()).limit(10).all()
    return render_template('lab/index.html', pending=pending, recent_completed=recent_completed)


@lab_bp.route('/catalog')
@login_required
def catalog():
    search = request.args.get('search', '')
    category = request.args.get('category', 'all')
    query = LabTestCatalog.query
    if search:
        query = query.filter(
            (LabTestCatalog.name.ilike(f'%{search}%')) |
            (LabTestCatalog.code.ilike(f'%{search}%'))
        )
    if category != 'all':
        query = query.filter_by(category=category)
    tests = query.order_by(LabTestCatalog.name).all()
    return render_template('lab/catalog.html', tests=tests, search=search, category=category)


@lab_bp.route('/catalog/new', methods=['GET', 'POST'])
@login_required
def new_catalog():
    if request.method == 'POST':
        test = LabTestCatalog(
            name=request.form.get('name'),
            code=request.form.get('code'),
            category=request.form.get('category'),
            normal_range=request.form.get('normal_range'),
            unit=request.form.get('unit'),
            price=float(request.form.get('price', 0) or 0),
            sample_type=request.form.get('sample_type'),
            turnaround_time=int(request.form.get('turnaround_time', 24) or 24),
            description=request.form.get('description'),
        )
        db.session.add(test)
        db.session.commit()
        flash(f'Lab test "{test.name}" added to catalog.', 'success')
        return redirect(url_for('lab.catalog'))
    return render_template('lab/new_catalog.html')


@lab_bp.route('/orders')
@login_required
def orders():
    status = request.args.get('status', 'all')
    query = LabTest.query
    if status != 'all':
        query = query.filter_by(status=status)
    tests = query.order_by(LabTest.test_date.desc()).all()
    return render_template('lab/orders.html', tests=tests, status=status)


@lab_bp.route('/orders/<int:id>/result', methods=['GET', 'POST'])
@login_required
def enter_result(id):
    test = LabTest.query.get_or_404(id)
    if request.method == 'POST':
        test.result = request.form.get('result')
        test.normal_range = request.form.get('normal_range')
        test.status = 'completed'
        test.notes = request.form.get('notes')
        db.session.commit()
        flash('Lab test result entered successfully.', 'success')
        return redirect(url_for('lab.orders'))
    return render_template('lab/enter_result.html', test=test)
