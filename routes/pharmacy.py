from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, Medicine, Prescription, Patient, PharmacySale, PharmacySaleItem
from datetime import datetime, date
import random
import string

pharmacy_bp = Blueprint('pharmacy', __name__, url_prefix='/pharmacy')


def generate_sale_number():
    return 'RX' + ''.join(random.choices(string.digits, k=6))


# ─── Inventory ────────────────────────────────────────────────────────────────

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
    if stock_filter == 'out':
        query = query.filter(Medicine.stock_quantity == 0)

    medicines = query.order_by(Medicine.name).all()
    categories = db.session.query(Medicine.category).distinct().filter(Medicine.category.isnot(None)).all()
    categories = [c[0] for c in categories]

    low_stock_count = Medicine.query.filter(Medicine.stock_quantity <= Medicine.reorder_level).count()
    out_of_stock_count = Medicine.query.filter(Medicine.stock_quantity == 0).count()

    # Expiry alert: medicines expiring within 30 days
    from datetime import timedelta
    expiry_alert = Medicine.query.filter(
        Medicine.expiry_date.isnot(None),
        Medicine.expiry_date <= date.today() + timedelta(days=30),
        Medicine.expiry_date >= date.today()
    ).count()

    return render_template('pharmacy/index.html',
        medicines=medicines,
        categories=categories,
        search=search,
        category=category,
        stock_filter=stock_filter,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
        expiry_alert=expiry_alert
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


# ─── API: search medicines (for POS autocomplete) ─────────────────────────────

@pharmacy_bp.route('/api/search')
@login_required
def api_search():
    q = request.args.get('q', '')
    medicines = Medicine.query.filter(
        (Medicine.name.ilike(f'%{q}%')) | (Medicine.generic_name.ilike(f'%{q}%'))
    ).filter(Medicine.stock_quantity > 0).limit(20).all()
    return jsonify([{
        'id': m.id,
        'name': m.name,
        'generic_name': m.generic_name or '',
        'unit': m.unit or '',
        'unit_price': m.unit_price,
        'stock_quantity': m.stock_quantity,
    } for m in medicines])


# ─── Prescriptions Queue ──────────────────────────────────────────────────────

@pharmacy_bp.route('/prescriptions')
@login_required
def prescriptions():
    prescriptions = Prescription.query.filter_by(status='active').order_by(Prescription.created_at.desc()).all()
    medicines = Medicine.query.filter(Medicine.stock_quantity > 0).order_by(Medicine.name).all()
    return render_template('pharmacy/prescriptions.html',
                           prescriptions=prescriptions, medicines=medicines)


@pharmacy_bp.route('/prescriptions/<int:id>/dispense', methods=['POST'])
@login_required
def dispense(id):
    """
    Dispense a prescription:
    - Deducts stock from inventory
    - Creates a PharmacySale record (linked to prescription)
    - Marks prescription as dispensed
    """
    prescription = Prescription.query.get_or_404(id)

    medicine_id = request.form.get('medicine_id')
    qty = int(request.form.get('quantity', 1))
    payment_method = request.form.get('payment_method', 'cash')

    med = None
    unit_price = 0.0

    if medicine_id:
        med = Medicine.query.get(int(medicine_id))

    if not med:
        # Try auto-match by name
        med = Medicine.query.filter(
            Medicine.name.ilike(f'%{prescription.medicine_name}%')
        ).first()

    if med:
        if med.stock_quantity < qty:
            flash(f'Insufficient stock! Only {med.stock_quantity} units of {med.name} available.', 'danger')
            return redirect(url_for('pharmacy.prescriptions'))
        med.stock_quantity -= qty
        unit_price = med.unit_price

    total = qty * unit_price

    # Get patient name from medical record chain
    patient_name = 'Unknown'
    patient_id_val = None
    if prescription.medical_record:
        rec = prescription.medical_record
        if rec.patient:
            patient_name = f'{rec.patient.first_name} {rec.patient.last_name}'
            patient_id_val = rec.patient.id

    sale = PharmacySale(
        sale_number=generate_sale_number(),
        patient_id=patient_id_val,
        patient_name=patient_name,
        prescription_id=prescription.id,
        sold_by=current_user.id,
        subtotal=total,
        discount=0,
        total_amount=total,
        payment_method=payment_method,
        payment_status='paid',
        notes=f'Prescription dispense — {prescription.dosage or ""} {prescription.frequency or ""}',
    )
    db.session.add(sale)
    db.session.flush()

    item = PharmacySaleItem(
        sale_id=sale.id,
        medicine_id=med.id if med else None,
        medicine_name=med.name if med else prescription.medicine_name,
        quantity=qty,
        unit_price=unit_price,
        total_price=total,
    )
    db.session.add(item)

    prescription.status = 'dispensed'
    db.session.commit()

    flash(f'{prescription.medicine_name} dispensed successfully! Sale #{sale.sale_number}', 'success')
    return redirect(url_for('pharmacy.sale_view', id=sale.id))


# ─── Counter / POS Sales ──────────────────────────────────────────────────────

@pharmacy_bp.route('/sales')
@login_required
def sales():
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    search = request.args.get('search', '')

    query = PharmacySale.query
    if search:
        query = query.filter(
            (PharmacySale.sale_number.ilike(f'%{search}%')) |
            (PharmacySale.patient_name.ilike(f'%{search}%'))
        )
    if date_from:
        query = query.filter(PharmacySale.sale_date >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(PharmacySale.sale_date <= datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59))

    sales_list = query.order_by(PharmacySale.sale_date.desc()).all()

    today_total = sum(s.total_amount for s in PharmacySale.query.filter(
        db.func.date(PharmacySale.sale_date) == date.today()
    ).all())

    return render_template('pharmacy/sales.html',
        sales=sales_list,
        today_total=today_total,
        date_from=date_from,
        date_to=date_to,
        search=search
    )


@pharmacy_bp.route('/sales/new', methods=['GET', 'POST'])
@login_required
def sale_new():
    """POS counter sale — sell medicines directly (walk-in or registered patient)."""
    patients = Patient.query.filter_by(status='active').order_by(Patient.first_name).all()

    if request.method == 'POST':
        patient_id = request.form.get('patient_id') or None
        patient_name = request.form.get('patient_name', '').strip() or 'Walk-in'
        payment_method = request.form.get('payment_method', 'cash')
        discount = float(request.form.get('discount', 0))
        notes = request.form.get('notes', '')

        medicine_ids = request.form.getlist('medicine_id[]')
        medicine_names = request.form.getlist('medicine_name[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')

        if not medicine_ids or not any(m.strip() for m in medicine_names):
            flash('Add at least one medicine to the sale.', 'danger')
            return redirect(url_for('pharmacy.sale_new'))

        subtotal = 0.0
        items_data = []
        errors = []

        for i, med_id in enumerate(medicine_ids):
            m_name = medicine_names[i].strip() if i < len(medicine_names) else ''
            if not m_name:
                continue
            qty = float(quantities[i]) if i < len(quantities) else 1
            uprice = float(unit_prices[i]) if i < len(unit_prices) else 0

            med = Medicine.query.get(int(med_id)) if med_id else None
            if med:
                if med.stock_quantity < qty:
                    errors.append(f'{med.name}: only {med.stock_quantity} in stock, requested {qty}')
                    continue

            items_data.append({'med': med, 'm_name': m_name, 'qty': qty, 'uprice': uprice})
            subtotal += qty * uprice

        if errors:
            for err in errors:
                flash(err, 'warning')
            if not items_data:
                return redirect(url_for('pharmacy.sale_new'))

        total = max(0, subtotal - discount)

        if patient_id:
            p = Patient.query.get(int(patient_id))
            if p:
                patient_name = f'{p.first_name} {p.last_name}'

        sale = PharmacySale(
            sale_number=generate_sale_number(),
            patient_id=int(patient_id) if patient_id else None,
            patient_name=patient_name,
            sold_by=current_user.id,
            subtotal=subtotal,
            discount=discount,
            total_amount=total,
            payment_method=payment_method,
            payment_status='paid',
            notes=notes,
        )
        db.session.add(sale)
        db.session.flush()

        for d in items_data:
            item = PharmacySaleItem(
                sale_id=sale.id,
                medicine_id=d['med'].id if d['med'] else None,
                medicine_name=d['m_name'],
                quantity=d['qty'],
                unit_price=d['uprice'],
                total_price=d['qty'] * d['uprice'],
            )
            db.session.add(item)
            if d['med']:
                d['med'].stock_quantity -= int(d['qty'])

        db.session.commit()
        flash(f'Sale {sale.sale_number} completed! Total: Rs. {total:,.0f}', 'success')
        return redirect(url_for('pharmacy.sale_view', id=sale.id))

    return render_template('pharmacy/sale_new.html', patients=patients, today=date.today())


@pharmacy_bp.route('/sales/<int:id>')
@login_required
def sale_view(id):
    sale = PharmacySale.query.get_or_404(id)
    return render_template('pharmacy/sale_view.html', sale=sale)


@pharmacy_bp.route('/sales/<int:id>/print')
@login_required
def sale_print(id):
    sale = PharmacySale.query.get_or_404(id)
    return render_template('pharmacy/sale_print.html', sale=sale)
