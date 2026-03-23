from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, SystemSetting

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


def get_setting(key, default=None):
    s = SystemSetting.query.filter_by(key=key).first()
    return s.value if s else default


def set_setting(key, value, description=None, category='general'):
    s = SystemSetting.query.filter_by(key=key).first()
    if s:
        s.value = value
    else:
        s = SystemSetting(key=key, value=value, description=description, category=category)
        db.session.add(s)
    db.session.commit()


@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        clinic_mode = '1' if request.form.get('clinic_mode') == '1' else '0'
        set_setting('clinic_mode', clinic_mode,
                    description='0=Hospital Mode, 1=Clinic Mode', category='system')

        hospital_name = request.form.get('hospital_name', '').strip()
        if hospital_name:
            set_setting('hospital_name', hospital_name,
                        description='Name shown in the system', category='general')

        hospital_address = request.form.get('hospital_address', '').strip()
        set_setting('hospital_address', hospital_address,
                    description='Hospital/Clinic address', category='general')

        hospital_phone = request.form.get('hospital_phone', '').strip()
        set_setting('hospital_phone', hospital_phone,
                    description='Contact phone number', category='general')

        currency = request.form.get('currency', 'PKR').strip()
        set_setting('currency', currency,
                    description='Currency symbol used in billing', category='finance')

        flash('Settings saved successfully!', 'success')
        return redirect(url_for('settings.index'))

    current = {
        'clinic_mode': get_setting('clinic_mode', '0'),
        'hospital_name': get_setting('hospital_name', 'MediCare Hospital'),
        'hospital_address': get_setting('hospital_address', ''),
        'hospital_phone': get_setting('hospital_phone', ''),
        'currency': get_setting('currency', 'PKR'),
    }
    return render_template('settings/index.html', current=current)
