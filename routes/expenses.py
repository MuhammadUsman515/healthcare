from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Expense, ExpenseCategory
from datetime import datetime, date
import random, string

expenses_bp = Blueprint('expenses', __name__, url_prefix='/expenses')


def gen_expense_number():
    return 'EXP' + ''.join(random.choices(string.digits, k=5))


@expenses_bp.route('/')
@login_required
def index():
    date_from = request.args.get('date_from', date.today().replace(day=1).isoformat())
    date_to = request.args.get('date_to', date.today().isoformat())
    cat_filter = request.args.get('category', '')

    df = datetime.strptime(date_from, '%Y-%m-%d').date()
    dt = datetime.strptime(date_to, '%Y-%m-%d').date()

    query = Expense.query.filter(Expense.expense_date.between(df, dt))
    if cat_filter:
        query = query.filter_by(category_id=int(cat_filter))

    expenses = query.order_by(Expense.expense_date.desc()).all()
    categories = ExpenseCategory.query.filter_by(is_active=True).order_by(ExpenseCategory.name).all()

    total = sum(e.amount for e in expenses)

    # Category-wise breakdown
    cat_totals = {}
    for e in expenses:
        cname = e.category.name if e.category else 'Uncategorized'
        cat_totals[cname] = cat_totals.get(cname, 0) + e.amount

    return render_template('expenses/index.html',
        expenses=expenses, categories=categories,
        total=total, cat_totals=cat_totals,
        date_from=date_from, date_to=date_to, cat_filter=cat_filter
    )


@expenses_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    categories = ExpenseCategory.query.filter_by(is_active=True).order_by(ExpenseCategory.name).all()

    if request.method == 'POST':
        exp_date_str = request.form.get('expense_date')
        exp_date = datetime.strptime(exp_date_str, '%Y-%m-%d').date() if exp_date_str else date.today()

        expense = Expense(
            expense_number=gen_expense_number(),
            category_id=int(request.form.get('category_id')) if request.form.get('category_id') else None,
            title=request.form.get('title'),
            amount=float(request.form.get('amount', 0)),
            expense_date=exp_date,
            payment_method=request.form.get('payment_method', 'cash'),
            vendor=request.form.get('vendor', ''),
            invoice_number=request.form.get('invoice_number', ''),
            notes=request.form.get('notes', ''),
            created_by=current_user.id
        )
        db.session.add(expense)
        db.session.commit()
        flash(f'Expense "{expense.title}" — Rs. {expense.amount:,.0f} recorded!', 'success')
        return redirect(url_for('expenses.index'))

    return render_template('expenses/new.html', categories=categories, today=date.today())


@expenses_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    expense = Expense.query.get_or_404(id)
    db.session.delete(expense)
    db.session.commit()
    flash('Expense deleted.', 'info')
    return redirect(url_for('expenses.index'))


# ─── CATEGORIES ───────────────────────────────────────────────────────────────

@expenses_bp.route('/categories')
@login_required
def categories():
    cats = ExpenseCategory.query.order_by(ExpenseCategory.name).all()
    return render_template('expenses/categories.html', categories=cats)


@expenses_bp.route('/categories/new', methods=['POST'])
@login_required
def new_category():
    name = request.form.get('name', '').strip()
    if name:
        cat = ExpenseCategory(name=name, description=request.form.get('description', ''))
        db.session.add(cat)
        db.session.commit()
        flash(f'Category "{name}" added!', 'success')
    return redirect(url_for('expenses.categories'))


@expenses_bp.route('/categories/<int:id>/delete', methods=['POST'])
@login_required
def delete_category(id):
    cat = ExpenseCategory.query.get_or_404(id)
    db.session.delete(cat)
    db.session.commit()
    flash('Category deleted.', 'info')
    return redirect(url_for('expenses.categories'))
