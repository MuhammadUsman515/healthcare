from flask import Flask
from flask_login import LoginManager
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

    # Core modules
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

    # Enterprise modules
    app.register_blueprint(staff_bp)
    app.register_blueprint(blood_bank_bp)
    app.register_blueprint(ambulance_bp)
    app.register_blueprint(opd_bp)
    app.register_blueprint(referrals_bp)
    app.register_blueprint(lab_bp)
    app.register_blueprint(po_bp)
    app.register_blueprint(audit_bp)

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
