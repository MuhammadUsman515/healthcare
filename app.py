from flask import Flask, redirect, url_for, request
from flask_login import LoginManager, current_user
from config import Config
from models import db, User
from routes.auth import auth_bp
from routes.main import main_bp
from routes.patients import patients_bp
from routes.doctors import doctors_bp
from routes.appointments import appointments_bp
from routes.billing import billing_bp
from routes.pharmacy import pharmacy_bp
from routes.wards import wards_bp
from routes.departments import departments_bp
from routes.reports import reports_bp
from routes.staff import staff_bp
from routes.blood_bank import blood_bank_bp
from routes.ambulance import ambulance_bp
from routes.opd import opd_bp
from routes.referrals import referrals_bp
from routes.lab import lab_bp
from routes.purchase_orders import po_bp
from routes.audit import audit_bp
from routes.settings import settings_bp
from routes.saas import saas_bp
from routes.ai import ai_bp
from routes.platform_admin import platform_admin_bp
from routes.onboarding import onboarding_bp
from routes.notifications import notifications_bp
from routes.billing_saas import billing_saas_bp
from routes.hr import hr_bp
from routes.expenses import expenses_bp
from routes.certificates import certificates_bp
from routes.insurance import insurance_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ── Context processor: inject brand settings into every template ──────────
    @app.context_processor
    def inject_settings():
        from models import SystemSetting, Organization
        try:
            mode = SystemSetting.query.filter_by(key='clinic_mode').first()
            clinic_mode = (mode.value == '1') if mode else False
            name_row = SystemSetting.query.filter_by(key='hospital_name').first()
            hospital_name = name_row.value if name_row else 'BizVinc HMS'
            currency_row = SystemSetting.query.filter_by(key='currency').first()
            currency = currency_row.value if currency_row else 'PKR'
        except Exception:
            clinic_mode = False
            hospital_name = 'BizVinc HMS'
            currency = 'PKR'

        # SaaS org context
        org = None
        trial_days_left = None
        subscription_status = None
        try:
            if current_user.is_authenticated and current_user.org_id:
                org = Organization.query.get(current_user.org_id)
                if org:
                    trial_days_left = org.trial_days_left
                    subscription_status = org.subscription_status
                    if org.name:
                        hospital_name = org.name
                    if org.currency:
                        currency = org.currency
                    # Sync clinic_mode with org plan_type
                    clinic_mode = (org.plan_type == 'clinic')
        except Exception:
            pass

        return dict(
            clinic_mode=clinic_mode,
            hospital_name=hospital_name,
            currency=currency,
            org=org,
            trial_days_left=trial_days_left,
            subscription_status=subscription_status,
        )

    # ── Public landing page ───────────────────────────────────────────────────
    @app.route('/')
    def landing():
        if current_user.is_authenticated:
            return redirect(url_for('main.dashboard'))
        from flask import render_template
        return render_template('landing.html')

    # ── Blueprints ────────────────────────────────────────────────────────────
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(doctors_bp)
    app.register_blueprint(appointments_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(pharmacy_bp)
    app.register_blueprint(wards_bp)
    app.register_blueprint(departments_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(blood_bank_bp)
    app.register_blueprint(ambulance_bp)
    app.register_blueprint(opd_bp)
    app.register_blueprint(referrals_bp)
    app.register_blueprint(lab_bp)
    app.register_blueprint(po_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(saas_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(platform_admin_bp)
    app.register_blueprint(onboarding_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(billing_saas_bp)
    app.register_blueprint(hr_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(certificates_bp)
    app.register_blueprint(insurance_bp)

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
