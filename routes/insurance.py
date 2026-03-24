from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, InsuranceClaim, InsuranceProvider, Patient, Bill
from datetime import datetime, date
import random, string

insurance_bp = Blueprint('insurance', __name__, url_prefix='/insurance')


def gen_claim_number():
    return 'CLM' + ''.join(random.choices(string.digits, k=6))


# ─── PROVIDERS ────────────────────────────────────────────────────────────────

@insurance_bp.route('/providers')
@login_required
def providers():
    providers_list = InsuranceProvider.query.order_by(InsuranceProvider.name).all()
    return render_template('insurance/providers.html', providers=providers_list)


@insurance_bp.route('/providers/new', methods=['GET', 'POST'])
@login_required
def new_provider():
    if request.method == 'POST':
        provider = InsuranceProvider(
            name=request.form.get('name'),
            code=request.form.get('code', ''),
            contact_person=request.form.get('contact_person', ''),
            phone=request.form.get('phone', ''),
            email=request.form.get('email', ''),
            address=request.form.get('address', ''),
            claim_process_days=int(request.form.get('claim_process_days', 30)),
            is_active=True
        )
        db.session.add(provider)
        db.session.commit()
        flash(f'{provider.name} added!', 'success')
        return redirect(url_for('insurance.providers'))
    return render_template('insurance/new_provider.html')


@insurance_bp.route('/providers/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_provider(id):
    p = InsuranceProvider.query.get_or_404(id)
    p.is_active = not p.is_active
    db.session.commit()
    flash(f'{p.name} {"activated" if p.is_active else "deactivated"}.', 'info')
    return redirect(url_for('insurance.providers'))


# ─── CLAIMS ───────────────────────────────────────────────────────────────────

@insurance_bp.route('/claims')
@login_required
def claims():
    status_filter = request.args.get('status', 'all')
    provider_filter = request.args.get('provider', '')

    query = InsuranceClaim.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    if provider_filter:
        query = query.filter_by(provider_id=int(provider_filter))

    claims_list = query.order_by(InsuranceClaim.created_at.desc()).all()
    providers_list = InsuranceProvider.query.filter_by(is_active=True).all()

    # Summary
    pending_count = InsuranceClaim.query.filter_by(status='pending').count()
    submitted_count = InsuranceClaim.query.filter(InsuranceClaim.status.in_(['submitted', 'under_review'])).count()
    total_claimed = sum(c.claim_amount for c in InsuranceClaim.query.all())
    total_approved = sum(c.approved_amount for c in InsuranceClaim.query.filter_by(status='settled').all())

    return render_template('insurance/claims.html',
        claims=claims_list, providers=providers_list,
        status_filter=status_filter, provider_filter=provider_filter,
        pending_count=pending_count, submitted_count=submitted_count,
        total_claimed=total_claimed, total_approved=total_approved
    )


@insurance_bp.route('/claims/new', methods=['GET', 'POST'])
@login_required
def new_claim():
    patients = Patient.query.filter_by(status='active').order_by(Patient.first_name).all()
    providers_list = InsuranceProvider.query.filter_by(is_active=True).order_by(InsuranceProvider.name).all()

    if request.method == 'POST':
        patient_id = int(request.form.get('patient_id'))
        submission_str = request.form.get('submission_date')
        submission_date = datetime.strptime(submission_str, '%Y-%m-%d').date() if submission_str else date.today()

        bill_id = request.form.get('bill_id') or None

        claim = InsuranceClaim(
            claim_number=gen_claim_number(),
            patient_id=patient_id,
            provider_id=int(request.form.get('provider_id')),
            bill_id=int(bill_id) if bill_id else None,
            policy_number=request.form.get('policy_number', ''),
            policy_holder_name=request.form.get('policy_holder_name', ''),
            claim_amount=float(request.form.get('claim_amount', 0)),
            status='submitted',
            submission_date=submission_date,
            notes=request.form.get('notes', ''),
            created_by=current_user.id
        )
        db.session.add(claim)
        db.session.commit()
        flash(f'Claim {claim.claim_number} submitted!', 'success')
        return redirect(url_for('insurance.view_claim', id=claim.id))

    # Get bills for selected patient (AJAX handled via JS redirect, or pre-fill)
    prefill_patient_id = request.args.get('patient_id')
    prefill_bill_id = request.args.get('bill_id')
    bills_list = []
    if prefill_patient_id:
        bills_list = Bill.query.filter_by(patient_id=int(prefill_patient_id)).order_by(Bill.bill_date.desc()).all()

    return render_template('insurance/new_claim.html',
        patients=patients, providers=providers_list,
        bills=bills_list, today=date.today(),
        prefill_patient_id=prefill_patient_id,
        prefill_bill_id=prefill_bill_id
    )


@insurance_bp.route('/claims/<int:id>')
@login_required
def view_claim(id):
    claim = InsuranceClaim.query.get_or_404(id)
    return render_template('insurance/view_claim.html', claim=claim)


@insurance_bp.route('/claims/<int:id>/update', methods=['POST'])
@login_required
def update_claim(id):
    claim = InsuranceClaim.query.get_or_404(id)
    new_status = request.form.get('status')
    approved_amount_str = request.form.get('approved_amount', '')
    settlement_date_str = request.form.get('settlement_date', '')

    claim.status = new_status
    if approved_amount_str:
        claim.approved_amount = float(approved_amount_str)
    if settlement_date_str:
        claim.settlement_date = datetime.strptime(settlement_date_str, '%Y-%m-%d').date()
    claim.rejection_reason = request.form.get('rejection_reason', '')
    claim.notes = request.form.get('notes', claim.notes)

    # If settled, update the linked bill's paid amount
    if new_status == 'settled' and claim.bill and claim.approved_amount:
        claim.bill.paid_amount += claim.approved_amount
        if claim.bill.paid_amount >= claim.bill.total_amount:
            claim.bill.payment_status = 'paid'
        elif claim.bill.paid_amount > 0:
            claim.bill.payment_status = 'partial'

    db.session.commit()
    flash(f'Claim {claim.claim_number} updated to {new_status}!', 'success')
    return redirect(url_for('insurance.view_claim', id=id))


@insurance_bp.route('/api/patient-bills/<int:patient_id>')
@login_required
def patient_bills_api(patient_id):
    from flask import jsonify
    bills = Bill.query.filter_by(patient_id=patient_id).order_by(Bill.bill_date.desc()).limit(20).all()
    return jsonify([{
        'id': b.id,
        'bill_number': b.bill_number,
        'total_amount': b.total_amount,
        'paid_amount': b.paid_amount,
        'status': b.payment_status,
    } for b in bills])
