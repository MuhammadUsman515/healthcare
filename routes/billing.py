from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from models import db, Bill, BillItem, Patient
from datetime import datetime, date, timedelta
import random
import string

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')


def generate_bill_number():
    return 'BILL' + ''.join(random.choices(string.digits, k=6))


@billing_bp.route('/')
@login_required
def index():
    status = request.args.get('status', 'all')
    search = request.args.get('search', '')

    query = Bill.query
    if status != 'all':
        query = query.filter_by(payment_status=status)
    if search:
        query = query.join(Patient).filter(
            (Patient.first_name.ilike(f'%{search}%')) |
            (Patient.last_name.ilike(f'%{search}%')) |
            (Bill.bill_number.ilike(f'%{search}%'))
        )

    bills = query.order_by(Bill.bill_date.desc()).all()
    return render_template('billing/index.html', bills=bills, status=status, search=search)


@billing_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    patients = Patient.query.filter_by(status='active').order_by(Patient.first_name).all()

    if request.method == 'POST':
        patient_id = int(request.form.get('patient_id'))
        due_date_str = request.form.get('due_date')
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else (date.today() + timedelta(days=30))

        descriptions = request.form.getlist('description[]')
        item_types = request.form.getlist('item_type[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')

        items = []
        subtotal = 0
        for i, desc in enumerate(descriptions):
            if desc.strip():
                qty = float(quantities[i]) if i < len(quantities) else 1
                uprice = float(unit_prices[i]) if i < len(unit_prices) else 0
                total = qty * uprice
                subtotal += total
                items.append(BillItem(
                    description=desc,
                    item_type=item_types[i] if i < len(item_types) else 'other',
                    quantity=qty,
                    unit_price=uprice,
                    total_price=total
                ))

        tax_rate = float(request.form.get('tax_rate', 0))
        discount = float(request.form.get('discount', 0))
        tax = subtotal * tax_rate / 100
        total = subtotal + tax - discount

        bill = Bill(
            bill_number=generate_bill_number(),
            patient_id=patient_id,
            due_date=due_date,
            subtotal=subtotal,
            tax=tax,
            discount=discount,
            total_amount=total,
            notes=request.form.get('notes'),
        )
        db.session.add(bill)
        db.session.flush()

        for item in items:
            item.bill_id = bill.id
            db.session.add(item)

        db.session.commit()
        flash(f'Bill {bill.bill_number} created successfully!', 'success')
        return redirect(url_for('billing.view', id=bill.id))

    patient_id = request.args.get('patient_id')
    return render_template('billing/new.html', patients=patients, patient_id=patient_id,
                           today=date.today(), default_due=date.today() + timedelta(days=30))


@billing_bp.route('/<int:id>')
@login_required
def view(id):
    bill = Bill.query.get_or_404(id)
    return render_template('billing/view.html', bill=bill)


@billing_bp.route('/<int:id>/payment', methods=['POST'])
@login_required
def add_payment(id):
    bill = Bill.query.get_or_404(id)
    amount = float(request.form.get('amount', 0))
    method = request.form.get('payment_method', 'cash')

    bill.paid_amount += amount
    bill.payment_method = method

    if bill.paid_amount >= bill.total_amount:
        bill.payment_status = 'paid'
    elif bill.paid_amount > 0:
        bill.payment_status = 'partial'

    db.session.commit()
    flash(f'Payment of ${amount:.2f} recorded successfully!', 'success')
    return redirect(url_for('billing.view', id=id))


@billing_bp.route('/<int:id>/print')
@login_required
def print_bill(id):
    bill = Bill.query.get_or_404(id)
    return render_template('billing/print.html', bill=bill)
