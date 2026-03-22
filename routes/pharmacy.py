from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from models import db, Medicine, Prescription
from datetime import datetime, date

pharmacy_bp = Blueprint('pharmacy', __name__, url_prefix='/pharmacy')


@pharmacy_bp.route('/')
@login_required
def index():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    stock_filter = request.args.get('stock', '')

    query = Medicine.query
    if search:
        query = query.filter(
            (Medicine.name.ilike(f'%{search}%')) |
            (Medicine.generic_name.ilike(f'%{search}%'))
        )
    if category:
        query = query.filter_by(category=category)
    if stock_filter == 'low':
        query = query.filter(Medicine.stock_quantity <= Medicine.reorder_level)

    medicines = query.order_by(Medicine.name).all()
    categories = db.session.query(Medicine.category).distinct().filter(Medicine.category.isnot(None)).all()
    categories = [c[0] for c in categories]

    low_stock_count = Medicine.query.filter(Medicine.stock_quantity <= Medicine.reorder_level).count()

    return render_template('pharmacy/index.html',
        medicines=medicines,
        categories=categories,
        search=search,
        category=category,
        stock_filter=stock_filter,
        low_stock_count=low_stock_count
    )


@pharmacy_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        expiry_str = request.form.get('expiry_date')
        expiry = datetime.strptime(expiry_str, '%Y-%m-%d').date() if expiry_str else None

        medicine = Medicine(
            name=request.form.get('name'),
            generic_name=request.form.get('generic_name'),
            category=request.form.get('category'),
            manufacturer=request.form.get('manufacturer'),
            unit=request.form.get('unit'),
            unit_price=float(request.form.get('unit_price') or 0),
            stock_quantity=int(request.form.get('stock_quantity') or 0),
            reorder_level=int(request.form.get('reorder_level') or 10),
            expiry_date=expiry,
            description=request.form.get('description'),
        )
        db.session.add(medicine)
        db.session.commit()
        flash(f'{medicine.name} added to pharmacy!', 'success')
        return redirect(url_for('pharmacy.index'))

    return render_template('pharmacy/new.html')


@pharmacy_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    medicine = Medicine.query.get_or_404(id)

    if request.method == 'POST':
        expiry_str = request.form.get('expiry_date')
        medicine.name = request.form.get('name')
        medicine.generic_name = request.form.get('generic_name')
        medicine.category = request.form.get('category')
        medicine.manufacturer = request.form.get('manufacturer')
        medicine.unit = request.form.get('unit')
        medicine.unit_price = float(request.form.get('unit_price') or 0)
        medicine.stock_quantity = int(request.form.get('stock_quantity') or 0)
        medicine.reorder_level = int(request.form.get('reorder_level') or 10)
        medicine.expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date() if expiry_str else None
        medicine.description = request.form.get('description')
        db.session.commit()
        flash(f'{medicine.name} updated successfully!', 'success')
        return redirect(url_for('pharmacy.index'))

    return render_template('pharmacy/edit.html', medicine=medicine)


@pharmacy_bp.route('/<int:id>/restock', methods=['POST'])
@login_required
def restock(id):
    medicine = Medicine.query.get_or_404(id)
    quantity = int(request.form.get('quantity', 0))
    medicine.stock_quantity += quantity
    db.session.commit()
    flash(f'Added {quantity} units to {medicine.name}. New stock: {medicine.stock_quantity}', 'success')
    return redirect(url_for('pharmacy.index'))


@pharmacy_bp.route('/prescriptions')
@login_required
def prescriptions():
    prescriptions = Prescription.query.filter_by(status='active').order_by(Prescription.created_at.desc()).all()
    return render_template('pharmacy/prescriptions.html', prescriptions=prescriptions)


@pharmacy_bp.route('/prescriptions/<int:id>/dispense', methods=['POST'])
@login_required
def dispense(id):
    prescription = Prescription.query.get_or_404(id)
    prescription.status = 'dispensed'
    db.session.commit()
    flash(f'{prescription.medicine_name} dispensed successfully!', 'success')
    return redirect(url_for('pharmacy.prescriptions'))
