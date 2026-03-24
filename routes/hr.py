from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, Staff, StaffAttendance, StaffLeave
from datetime import datetime, date, timedelta
import calendar

hr_bp = Blueprint('hr', __name__, url_prefix='/hr')


# ─── ATTENDANCE ───────────────────────────────────────────────────────────────

@hr_bp.route('/attendance')
@login_required
def attendance():
    sel_date = request.args.get('date', date.today().isoformat())
    try:
        sel_date_obj = datetime.strptime(sel_date, '%Y-%m-%d').date()
    except ValueError:
        sel_date_obj = date.today()

    dept_filter = request.args.get('dept', '')
    staff_list = Staff.query.filter_by(status='active')
    if dept_filter:
        staff_list = staff_list.filter_by(department_id=int(dept_filter))
    staff_list = staff_list.order_by(Staff.first_name).all()

    # Get existing records for selected date
    existing = {a.staff_id: a for a in StaffAttendance.query.filter_by(date=sel_date_obj).all()}

    # Summary counts
    present = sum(1 for a in existing.values() if a.status in ('present', 'late', 'half_day'))
    absent = sum(1 for a in existing.values() if a.status == 'absent')
    on_leave = sum(1 for a in existing.values() if a.status == 'on_leave')

    return render_template('hr/attendance.html',
        staff_list=staff_list,
        existing=existing,
        sel_date=sel_date,
        sel_date_obj=sel_date_obj,
        present=present, absent=absent, on_leave=on_leave,
        today=date.today()
    )


@hr_bp.route('/attendance/save', methods=['POST'])
@login_required
def save_attendance():
    att_date_str = request.form.get('att_date')
    att_date = datetime.strptime(att_date_str, '%Y-%m-%d').date()

    staff_ids = request.form.getlist('staff_id[]')
    statuses = request.form.getlist('status[]')
    check_ins = request.form.getlist('check_in[]')
    check_outs = request.form.getlist('check_out[]')
    notes_list = request.form.getlist('notes[]')

    saved = 0
    for i, sid in enumerate(staff_ids):
        sid = int(sid)
        status = statuses[i] if i < len(statuses) else 'present'
        check_in = check_ins[i] if i < len(check_ins) else ''
        check_out = check_outs[i] if i < len(check_outs) else ''
        notes = notes_list[i] if i < len(notes_list) else ''

        rec = StaffAttendance.query.filter_by(staff_id=sid, date=att_date).first()
        if rec:
            rec.status = status
            rec.check_in = check_in or None
            rec.check_out = check_out or None
            rec.notes = notes or None
            rec.marked_by = current_user.id
        else:
            rec = StaffAttendance(
                staff_id=sid, date=att_date, status=status,
                check_in=check_in or None, check_out=check_out or None,
                notes=notes or None, marked_by=current_user.id
            )
            db.session.add(rec)
        saved += 1

    db.session.commit()
    flash(f'Attendance saved for {saved} staff on {att_date.strftime("%d %b %Y")}!', 'success')
    return redirect(url_for('hr.attendance', date=att_date_str))


@hr_bp.route('/attendance/report')
@login_required
def attendance_report():
    year = int(request.args.get('year', date.today().year))
    month = int(request.args.get('month', date.today().month))

    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    all_dates = [first_day + timedelta(days=i) for i in range((last_day - first_day).days + 1)]

    staff_list = Staff.query.filter_by(status='active').order_by(Staff.first_name).all()
    records = StaffAttendance.query.filter(
        StaffAttendance.date.between(first_day, last_day)
    ).all()

    # attendance_map[staff_id][date] = status
    att_map = {}
    for r in records:
        att_map.setdefault(r.staff_id, {})[r.date] = r.status

    months = [(i, calendar.month_name[i]) for i in range(1, 13)]
    years = list(range(date.today().year - 2, date.today().year + 1))

    return render_template('hr/attendance_report.html',
        staff_list=staff_list, all_dates=all_dates,
        att_map=att_map, year=year, month=month,
        months=months, years=years,
        month_name=calendar.month_name[month]
    )


# ─── LEAVES ───────────────────────────────────────────────────────────────────

@hr_bp.route('/leaves')
@login_required
def leaves():
    status_filter = request.args.get('status', 'all')
    query = StaffLeave.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    leaves_list = query.order_by(StaffLeave.created_at.desc()).all()

    pending_count = StaffLeave.query.filter_by(status='pending').count()

    return render_template('hr/leaves.html',
        leaves=leaves_list, status_filter=status_filter,
        pending_count=pending_count
    )


@hr_bp.route('/leaves/apply', methods=['GET', 'POST'])
@login_required
def apply_leave():
    staff_list = Staff.query.filter_by(status='active').order_by(Staff.first_name).all()

    if request.method == 'POST':
        staff_id = int(request.form.get('staff_id'))
        from_str = request.form.get('from_date')
        to_str = request.form.get('to_date')
        from_date = datetime.strptime(from_str, '%Y-%m-%d').date()
        to_date = datetime.strptime(to_str, '%Y-%m-%d').date()
        days = (to_date - from_date).days + 1

        leave = StaffLeave(
            staff_id=staff_id,
            leave_type=request.form.get('leave_type'),
            from_date=from_date,
            to_date=to_date,
            days=days,
            reason=request.form.get('reason'),
            status='pending'
        )
        db.session.add(leave)
        db.session.commit()
        flash('Leave application submitted!', 'success')
        return redirect(url_for('hr.leaves'))

    return render_template('hr/apply_leave.html', staff_list=staff_list, today=date.today())


@hr_bp.route('/leaves/<int:id>/approve', methods=['POST'])
@login_required
def approve_leave(id):
    leave = StaffLeave.query.get_or_404(id)
    action = request.form.get('action')  # approve or reject

    if action == 'approve':
        leave.status = 'approved'
        leave.approved_by = current_user.id
        leave.approved_at = datetime.utcnow()
        # Mark attendance as on_leave for each day
        current = leave.from_date
        while current <= leave.to_date:
            rec = StaffAttendance.query.filter_by(staff_id=leave.staff_id, date=current).first()
            if not rec:
                rec = StaffAttendance(staff_id=leave.staff_id, date=current, status='on_leave', marked_by=current_user.id)
                db.session.add(rec)
            else:
                rec.status = 'on_leave'
            current += timedelta(days=1)
        flash(f'Leave approved for {leave.staff.full_name}!', 'success')
    else:
        leave.status = 'rejected'
        leave.rejection_reason = request.form.get('rejection_reason', '')
        leave.approved_by = current_user.id
        leave.approved_at = datetime.utcnow()
        flash(f'Leave rejected.', 'warning')

    db.session.commit()
    return redirect(url_for('hr.leaves'))


@hr_bp.route('/leaves/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_leave(id):
    leave = StaffLeave.query.get_or_404(id)
    leave.status = 'cancelled'
    db.session.commit()
    flash('Leave cancelled.', 'info')
    return redirect(url_for('hr.leaves'))
