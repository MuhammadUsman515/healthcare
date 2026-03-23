from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, PurchaseOrder, PurchaseOrderItem, Supplier, Medicine
from datetime import datetime, date
import random
import string

po_bp = Blueprint('purchase_orders', __name__, url_prefix='/purchase-orders')


def generate_po_number():
    return 'PO' + ''.join(random.choices(string.digits, k=7))


@po_bp.route('/')
@login_required
def index():
    status = request.args.get('status', 'all')
    query = PurchaseOrder.query
    if status != 'all':
        query = query.filter_by(status=status)
    orders = query.order_by(PurchaseOrder.order_date.desc()).all()
    return render_template('purchase_orders/index.html', orders=orders, status=status)


@po_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    suppliers = Supplier.query.filter_by(status='active').order_by(Supplier.name).all()
    medicines = Medicine.query.order_by(Medicine.name).all()
    if request.method == 'POST':
        expected_str = request.form.get('expected_date')
        po = PurchaseOrder(
            po_number=generate_po_number(),
            supplier_id=int(request.form.get('supplier_id')),
            ordered_by=current_user.id,
            order_date=date.today(),
            expected_date=datetime.strptime(expected_str, '%Y-%m-%d').date() if expected_str else None,
            notes=request.form.get('notes'),
        )
        db.session.add(po)
        db.session.flush()

        medicine_ids = request.form.getlist('medicine_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')

        subtotal = 0
        for i in range(len(medicine_ids)):
            if not medicine_ids[i]:
                continue
            med = Medicine.query.get(int(medicine_ids[i]))
            qty = int(quantities[i] or 0)
            price = float(unit_prices[i] or 0)
            total = qty * price
            subtotal += total
            item = PurchaseOrderItem(
                po_id=po.id,
                medicine_id=med.id,
                item_name=med.name,
                quantity=qty,
                unit_price=price,
                total_price=total,
            )
            db.session.add(item)

        po.subtotal = subtotal
        po.total_amount = subtotal
        db.session.commit()
        flash(f'Purchase Order {po.po_number} created successfully!', 'success')
        return redirect(url_for('purchase_orders.view', id=po.id))
    return render_template('purchase_orders/new.html', suppliers=suppliers, medicines=medicines)


@po_bp.route('/<int:id>')
@login_required
def view(id):
    po = PurchaseOrder.query.get_or_404(id)
    return render_template('purchase_orders/view.html', po=po)


@po_bp.route('/<int:id>/approve', methods=['POST'])
@login_required
def approve(id):
    po = PurchaseOrder.query.get_or_404(id)
    po.status = 'approved'
    db.session.commit()
    flash(f'Purchase Order {po.po_number} approved.', 'success')
    return redirect(url_for('purchase_orders.view', id=po.id))


@po_bp.route('/<int:id>/receive', methods=['POST'])
@login_required
def receive(id):
    po = PurchaseOrder.query.get_or_404(id)
    po.status = 'received'
    po.received_date = date.today()
    for item in po.items:
        if item.medicine_id:
            med = Medicine.query.get(item.medicine_id)
            if med:
                med.stock_quantity += item.quantity
    db.session.commit()
    flash(f'Purchase Order {po.po_number} received. Medicine stock updated.', 'success')
    return redirect(url_for('purchase_orders.view', id=po.id))


@po_bp.route('/suppliers')
@login_required
def suppliers():
    all_suppliers = Supplier.query.order_by(Supplier.name).all()
    return render_template('purchase_orders/suppliers.html', suppliers=all_suppliers)


@po_bp.route('/suppliers/new', methods=['GET', 'POST'])
@login_required
def new_supplier():
    if request.method == 'POST':
        supplier = Supplier(
            name=request.form.get('name'),
            contact_person=request.form.get('contact_person'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            address=request.form.get('address'),
            city=request.form.get('city'),
            country=request.form.get('country'),
            tax_id=request.form.get('tax_id'),
            payment_terms=request.form.get('payment_terms'),
        )
        db.session.add(supplier)
        db.session.commit()
        flash(f'Supplier {supplier.name} added successfully!', 'success')
        return redirect(url_for('purchase_orders.suppliers'))
    return render_template('purchase_orders/new_supplier.html')
