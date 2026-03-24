from datetime import datetime
import json
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ─── PLAN TIERS & FEATURES ────────────────────────────────────────────────────

PLAN_FEATURES = {
    'basic': {
        'label': 'Basic',
        'max_users': 5,
        'max_branches': 1,
        'max_patients_per_month': 200,
        'modules': ['patients', 'appointments', 'consultation', 'prescription', 'billing', 'reports'],
        'ai': False,
        'reminders': False,
        'lab': False,
        'pharmacy': False,
        'ipd': False,
        'multi_branch': False,
        'api_access': False,
        'custom_templates': False,
        'whatsapp': False,
    },
    'standard': {
        'label': 'Standard',
        'max_users': 15,
        'max_branches': 3,
        'max_patients_per_month': 1000,
        'modules': ['patients', 'appointments', 'consultation', 'prescription', 'billing',
                    'reports', 'opd', 'staff', 'departments', 'reminders', 'ai_summary'],
        'ai': True,
        'reminders': True,
        'lab': False,
        'pharmacy': False,
        'ipd': False,
        'multi_branch': True,
        'api_access': False,
        'custom_templates': True,
        'whatsapp': True,
    },
    'pro': {
        'label': 'Pro',
        'max_users': 50,
        'max_branches': 10,
        'max_patients_per_month': 5000,
        'modules': ['patients', 'appointments', 'consultation', 'prescription', 'billing',
                    'reports', 'opd', 'staff', 'departments', 'reminders', 'ai_summary',
                    'lab', 'pharmacy', 'inventory', 'blood_bank', 'ambulance', 'referrals',
                    'ai_predictive', 'ai_business'],
        'ai': True,
        'reminders': True,
        'lab': True,
        'pharmacy': True,
        'ipd': False,
        'multi_branch': True,
        'api_access': True,
        'custom_templates': True,
        'whatsapp': True,
    },
    'enterprise': {
        'label': 'Enterprise',
        'max_users': 9999,
        'max_branches': 9999,
        'max_patients_per_month': 99999,
        'modules': ['all'],
        'ai': True,
        'reminders': True,
        'lab': True,
        'pharmacy': True,
        'ipd': True,
        'multi_branch': True,
        'api_access': True,
        'custom_templates': True,
        'whatsapp': True,
    },
}


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='patient')  # admin, doctor, nurse, receptionist, patient
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)

    doctor = db.relationship('Doctor', backref='user', uselist=False)
    patient = db.relationship('Patient', backref='user', uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    head_doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    doctors = db.relationship('Doctor', backref='department', foreign_keys='Doctor.department_id')
    wards = db.relationship('Ward', backref='department')

    def __repr__(self):
        return f'<Department {self.name}>'


class Doctor(db.Model):
    __tablename__ = 'doctors'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    license_number = db.Column(db.String(50), unique=True)
    qualification = db.Column(db.String(200))
    experience_years = db.Column(db.Integer, default=0)
    consultation_fee = db.Column(db.Float, default=0.0)
    available_days = db.Column(db.String(100), default='Mon,Tue,Wed,Thu,Fri')
    available_from = db.Column(db.String(10), default='09:00')
    available_to = db.Column(db.String(10), default='17:00')
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    appointments = db.relationship('Appointment', backref='doctor')
    medical_records = db.relationship('MedicalRecord', backref='doctor')

    @property
    def full_name(self):
        return f'Dr. {self.first_name} {self.last_name}'

    def __repr__(self):
        return f'<Doctor {self.full_name}>'


class Patient(db.Model):
    __tablename__ = 'patients'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    patient_id = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    blood_group = db.Column(db.String(5))
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    emergency_contact_name = db.Column(db.String(100))
    emergency_contact_phone = db.Column(db.String(20))
    emergency_contact_relation = db.Column(db.String(50))
    allergies = db.Column(db.Text)
    chronic_conditions = db.Column(db.Text)
    insurance_provider = db.Column(db.String(100))
    insurance_number = db.Column(db.String(50))
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    appointments = db.relationship('Appointment', backref='patient')
    medical_records = db.relationship('MedicalRecord', backref='patient')
    bills = db.relationship('Bill', backref='patient')
    admissions = db.relationship('Admission', backref='patient')

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def age(self):
        today = datetime.today().date()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    def __repr__(self):
        return f'<Patient {self.full_name}>'


class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    appointment_id = db.Column(db.String(20), unique=True, nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.String(10), nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, completed, cancelled, no-show
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    medical_record = db.relationship('MedicalRecord', backref='appointment', uselist=False)

    def __repr__(self):
        return f'<Appointment {self.appointment_id}>'


class MedicalRecord(db.Model):
    __tablename__ = 'medical_records'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=True)
    visit_date = db.Column(db.DateTime, default=datetime.utcnow)
    chief_complaint = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    treatment_plan = db.Column(db.Text)
    vitals_bp = db.Column(db.String(20))
    vitals_pulse = db.Column(db.String(10))
    vitals_temperature = db.Column(db.String(10))
    vitals_weight = db.Column(db.String(10))
    vitals_height = db.Column(db.String(10))
    vitals_oxygen = db.Column(db.String(10))
    notes = db.Column(db.Text)
    follow_up_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    prescriptions = db.relationship('Prescription', backref='medical_record')
    lab_tests = db.relationship('LabTest', backref='medical_record')

    def __repr__(self):
        return f'<MedicalRecord {self.id}>'


class Prescription(db.Model):
    __tablename__ = 'prescriptions'
    id = db.Column(db.Integer, primary_key=True)
    medical_record_id = db.Column(db.Integer, db.ForeignKey('medical_records.id'), nullable=False)
    medicine_name = db.Column(db.String(200), nullable=False)
    dosage = db.Column(db.String(100))
    frequency = db.Column(db.String(100))
    duration = db.Column(db.String(100))
    instructions = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')  # active, dispensed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Prescription {self.medicine_name}>'


class LabTest(db.Model):
    __tablename__ = 'lab_tests'
    id = db.Column(db.Integer, primary_key=True)
    medical_record_id = db.Column(db.Integer, db.ForeignKey('medical_records.id'), nullable=False)
    test_name = db.Column(db.String(200), nullable=False)
    test_date = db.Column(db.DateTime, default=datetime.utcnow)
    result = db.Column(db.Text)
    normal_range = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')  # pending, completed, cancelled
    notes = db.Column(db.Text)

    def __repr__(self):
        return f'<LabTest {self.test_name}>'


class Ward(db.Model):
    __tablename__ = 'wards'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    ward_type = db.Column(db.String(50))  # general, icu, private, semi-private
    total_beds = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    beds = db.relationship('Bed', backref='ward')

    @property
    def available_beds(self):
        return sum(1 for b in self.beds if b.status == 'available')

    def __repr__(self):
        return f'<Ward {self.name}>'


class Bed(db.Model):
    __tablename__ = 'beds'
    id = db.Column(db.Integer, primary_key=True)
    bed_number = db.Column(db.String(20), nullable=False)
    ward_id = db.Column(db.Integer, db.ForeignKey('wards.id'), nullable=False)
    status = db.Column(db.String(20), default='available')  # available, occupied, maintenance
    bed_type = db.Column(db.String(50), default='standard')
    daily_rate = db.Column(db.Float, default=0.0)

    admissions = db.relationship('Admission', backref='bed')

    def __repr__(self):
        return f'<Bed {self.bed_number}>'


class Admission(db.Model):
    __tablename__ = 'admissions'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    admission_id = db.Column(db.String(20), unique=True, nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    bed_id = db.Column(db.Integer, db.ForeignKey('beds.id'), nullable=True)
    admitting_doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=True)
    admission_date = db.Column(db.DateTime, default=datetime.utcnow)
    discharge_date = db.Column(db.DateTime)
    diagnosis = db.Column(db.Text)
    status = db.Column(db.String(20), default='admitted')  # admitted, discharged
    notes = db.Column(db.Text)

    admitting_doctor = db.relationship('Doctor', backref='admissions')

    def __repr__(self):
        return f'<Admission {self.admission_id}>'


class Medicine(db.Model):
    __tablename__ = 'medicines'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    generic_name = db.Column(db.String(200))
    category = db.Column(db.String(100))
    manufacturer = db.Column(db.String(200))
    unit = db.Column(db.String(50))
    unit_price = db.Column(db.Float, default=0.0)
    stock_quantity = db.Column(db.Integer, default=0)
    reorder_level = db.Column(db.Integer, default=10)
    expiry_date = db.Column(db.Date)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.reorder_level

    def __repr__(self):
        return f'<Medicine {self.name}>'


class Bill(db.Model):
    __tablename__ = 'bills'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    bill_number = db.Column(db.String(20), unique=True, nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    bill_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.Date)
    subtotal = db.Column(db.Float, default=0.0)
    tax = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    paid_amount = db.Column(db.Float, default=0.0)
    payment_status = db.Column(db.String(20), default='pending')  # pending, partial, paid
    payment_method = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('BillItem', backref='bill', cascade='all, delete-orphan')

    @property
    def balance_due(self):
        return self.total_amount - self.paid_amount

    def __repr__(self):
        return f'<Bill {self.bill_number}>'


class BillItem(db.Model):
    __tablename__ = 'bill_items'
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.id'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    item_type = db.Column(db.String(50))  # consultation, procedure, medicine, lab, room
    quantity = db.Column(db.Float, default=1)
    unit_price = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, default=0.0)

    def __repr__(self):
        return f'<BillItem {self.description}>'


class Staff(db.Model):
    __tablename__ = 'staff'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # nurse, receptionist, pharmacist, lab_tech
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    employee_id = db.Column(db.String(20), unique=True)
    join_date = db.Column(db.Date)
    shift = db.Column(db.String(20), default='morning')  # morning, afternoon, night
    salary = db.Column(db.Float, default=0.0)
    address = db.Column(db.Text)
    emergency_contact = db.Column(db.String(100))
    emergency_phone = db.Column(db.String(20))
    qualification = db.Column(db.String(200))
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_rel = db.relationship('User', backref='staff_profile', foreign_keys=[user_id])
    dept = db.relationship('Department', backref='staff_members', foreign_keys=[department_id])

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def __repr__(self):
        return f'<Staff {self.full_name}>'


# ─── ENTERPRISE MODELS ────────────────────────────────────────────────────────

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='info')  # info, warning, success, danger
    icon = db.Column(db.String(50), default='bell')
    link = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='notifications')

    def __repr__(self):
        return f'<Notification {self.title}>'


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(100))
    resource_id = db.Column(db.Integer)
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(500))
    status = db.Column(db.String(20), default='success')  # success, failure
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='audit_logs')

    def __repr__(self):
        return f'<AuditLog {self.action}>'


class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(300))
    category = db.Column(db.String(50), default='general')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<SystemSetting {self.key}>'


class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    contact_person = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100), default='Pakistan')
    tax_id = db.Column(db.String(50))
    payment_terms = db.Column(db.String(100))
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    purchase_orders = db.relationship('PurchaseOrder', backref='supplier')

    def __repr__(self):
        return f'<Supplier {self.name}>'


class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id = db.Column(db.Integer, primary_key=True)
    po_number = db.Column(db.String(30), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    ordered_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    expected_date = db.Column(db.Date)
    received_date = db.Column(db.DateTime)
    subtotal = db.Column(db.Float, default=0.0)
    tax = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='pending')  # pending, approved, received, cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('PurchaseOrderItem', backref='purchase_order', cascade='all, delete-orphan')
    ordered_by_user = db.relationship('User', backref='purchase_orders')

    @property
    def balance_due(self):
        return self.total_amount

    def __repr__(self):
        return f'<PurchaseOrder {self.po_number}>'


class PurchaseOrderItem(db.Model):
    __tablename__ = 'purchase_order_items'
    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id'), nullable=True)
    item_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    unit_price = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, default=0.0)
    received_quantity = db.Column(db.Integer, default=0)

    medicine = db.relationship('Medicine', backref='po_items')

    def __repr__(self):
        return f'<POItem {self.item_name}>'


class OPDQueue(db.Model):
    __tablename__ = 'opd_queue'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    token_number = db.Column(db.String(20), unique=True, nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    priority = db.Column(db.String(20), default='normal')  # normal, urgent, emergency
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='waiting')  # waiting, in_consultation, completed, cancelled
    check_in_time = db.Column(db.DateTime, default=datetime.utcnow)
    consultation_start = db.Column(db.DateTime)
    consultation_end = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    queue_date = db.Column(db.Date, default=datetime.utcnow)

    patient = db.relationship('Patient', backref='opd_queue')
    doctor = db.relationship('Doctor', backref='opd_queue')
    dept = db.relationship('Department', backref='opd_queue')

    def __repr__(self):
        return f'<OPDQueue {self.token_number}>'


class BloodInventory(db.Model):
    __tablename__ = 'blood_inventory'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    blood_group = db.Column(db.String(5), nullable=False)  # A+, A-, B+, B-, O+, O-, AB+, AB-
    units_available = db.Column(db.Integer, default=0)
    units_reserved = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Blood {self.blood_group}>'


class BloodRequest(db.Model):
    __tablename__ = 'blood_requests'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    request_number = db.Column(db.String(30), unique=True, nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=True)
    blood_group = db.Column(db.String(5), nullable=False)
    units_required = db.Column(db.Integer, default=1)
    units_issued = db.Column(db.Integer, default=0)
    purpose = db.Column(db.String(200))
    urgency = db.Column(db.String(20), default='normal')  # normal, urgent, emergency
    status = db.Column(db.String(20), default='pending')  # pending, approved, issued, cancelled
    request_date = db.Column(db.DateTime, default=datetime.utcnow)
    issue_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)

    patient = db.relationship('Patient', backref='blood_requests')
    doctor = db.relationship('Doctor', backref='blood_requests')

    def __repr__(self):
        return f'<BloodRequest {self.request_number}>'


class Ambulance(db.Model):
    __tablename__ = 'ambulances'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    vehicle_number = db.Column(db.String(30), unique=True, nullable=False)
    vehicle_type = db.Column(db.String(50), default='basic')  # basic, advanced, neonatal
    driver_name = db.Column(db.String(100))
    driver_phone = db.Column(db.String(20))
    status = db.Column(db.String(20), default='available')  # available, dispatched, maintenance
    last_service_date = db.Column(db.Date)
    gps_tracking = db.Column(db.String(200))
    equipment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    dispatches = db.relationship('AmbulanceDispatch', backref='ambulance')

    def __repr__(self):
        return f'<Ambulance {self.vehicle_number}>'


class AmbulanceDispatch(db.Model):
    __tablename__ = 'ambulance_dispatches'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    dispatch_number = db.Column(db.String(30), unique=True, nullable=False)
    ambulance_id = db.Column(db.Integer, db.ForeignKey('ambulances.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=True)
    pickup_address = db.Column(db.Text, nullable=False)
    destination = db.Column(db.String(200))
    caller_name = db.Column(db.String(100))
    caller_phone = db.Column(db.String(20))
    dispatch_time = db.Column(db.DateTime, default=datetime.utcnow)
    pickup_time = db.Column(db.DateTime)
    arrival_time = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='dispatched')  # dispatched, en_route, arrived, completed, cancelled
    notes = db.Column(db.Text)

    patient = db.relationship('Patient', backref='ambulance_dispatches')

    def __repr__(self):
        return f'<AmbulanceDispatch {self.dispatch_number}>'


class Referral(db.Model):
    __tablename__ = 'referrals'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    referral_number = db.Column(db.String(30), unique=True, nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    referring_doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    referred_to_doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=True)
    referred_to_department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    referred_to_hospital = db.Column(db.String(200))
    reason = db.Column(db.Text, nullable=False)
    urgency = db.Column(db.String(20), default='routine')  # routine, urgent, emergency
    status = db.Column(db.String(20), default='pending')  # pending, accepted, completed, cancelled
    referral_date = db.Column(db.DateTime, default=datetime.utcnow)
    appointment_date = db.Column(db.Date)
    notes = db.Column(db.Text)

    patient = db.relationship('Patient', backref='referrals')
    referring_doctor = db.relationship('Doctor', foreign_keys=[referring_doctor_id], backref='referrals_made')
    referred_doctor = db.relationship('Doctor', foreign_keys=[referred_to_doctor_id], backref='referrals_received')
    referred_department = db.relationship('Department', backref='referrals')

    def __repr__(self):
        return f'<Referral {self.referral_number}>'


class LabTestCatalog(db.Model):
    __tablename__ = 'lab_test_catalog'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    code = db.Column(db.String(20), unique=True)
    category = db.Column(db.String(100))  # Hematology, Biochemistry, Microbiology, Radiology, etc.
    normal_range = db.Column(db.String(200))
    unit = db.Column(db.String(50))
    price = db.Column(db.Float, default=0.0)
    sample_type = db.Column(db.String(100))  # Blood, Urine, Stool, etc.
    turnaround_time = db.Column(db.String(50))  # e.g. "4 hours", "1 day"
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<LabTestCatalog {self.name}>'


# ─── SAAS MODELS ──────────────────────────────────────────────────────────────

PLAN_PRICING = {
    'PKR': {'clinic': 450,   'hospital': 1000,  'symbol': '₨',   'name': 'Pakistani Rupee'},
    'USD': {'clinic': 2,     'hospital': 4,     'symbol': '$',   'name': 'US Dollar'},
    'EUR': {'clinic': 2,     'hospital': 4,     'symbol': '€',   'name': 'Euro'},
    'GBP': {'clinic': 1.5,   'hospital': 3,     'symbol': '£',   'name': 'British Pound'},
    'SAR': {'clinic': 6,     'hospital': 14,    'symbol': '﷼',   'name': 'Saudi Riyal'},
    'AED': {'clinic': 6,     'hospital': 14,    'symbol': 'د.إ', 'name': 'UAE Dirham'},
    'INR': {'clinic': 170,   'hospital': 380,   'symbol': '₹',   'name': 'Indian Rupee'},
    'BDT': {'clinic': 220,   'hospital': 500,   'symbol': '৳',   'name': 'Bangladeshi Taka'},
    'EGP': {'clinic': 60,    'hospital': 140,   'symbol': 'E£',  'name': 'Egyptian Pound'},
    'NGN': {'clinic': 1800,  'hospital': 4000,  'symbol': '₦',   'name': 'Nigerian Naira'},
    'TRY': {'clinic': 65,    'hospital': 145,   'symbol': '₺',   'name': 'Turkish Lira'},
    'MYR': {'clinic': 9,     'hospital': 20,    'symbol': 'RM',  'name': 'Malaysian Ringgit'},
}


class Organization(db.Model):
    __tablename__ = 'organizations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    plan_type = db.Column(db.String(20), default='clinic')  # clinic, hospital
    country = db.Column(db.String(100), default='Pakistan')
    currency = db.Column(db.String(10), default='PKR')
    contact_email = db.Column(db.String(120), nullable=False)
    contact_phone = db.Column(db.String(30))
    address = db.Column(db.Text)
    logo_url = db.Column(db.String(500))
    trial_start = db.Column(db.DateTime, default=datetime.utcnow)
    trial_end = db.Column(db.DateTime)
    subscription_status = db.Column(db.String(20), default='trial')  # trial, active, expired, cancelled
    max_users = db.Column(db.Integer, default=5)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship('User', backref='organization', foreign_keys='User.org_id')

    @property
    def trial_days_left(self):
        if self.trial_end:
            delta = self.trial_end - datetime.utcnow()
            return max(0, delta.days)
        return 0

    @property
    def is_trial_active(self):
        return self.subscription_status == 'trial' and self.trial_days_left > 0

    @property
    def is_active(self):
        return self.subscription_status in ('trial', 'active') and (
            self.subscription_status == 'active' or self.trial_days_left > 0
        )

    @property
    def price_per_user(self):
        pricing = PLAN_PRICING.get(self.currency, PLAN_PRICING['PKR'])
        return pricing[self.plan_type]

    @property
    def currency_symbol(self):
        pricing = PLAN_PRICING.get(self.currency, PLAN_PRICING['PKR'])
        return pricing['symbol']

    def __repr__(self):
        return f'<Organization {self.name}>'

    def has_feature(self, feature):
        """Check if this org's plan includes a feature."""
        features = PLAN_FEATURES.get(self.plan_type, PLAN_FEATURES['basic'])
        return features.get(feature, False)

    def get_plan_features(self):
        return PLAN_FEATURES.get(self.plan_type, PLAN_FEATURES['basic'])


# ─── BRANCH MODEL ─────────────────────────────────────────────────────────────

class Branch(db.Model):
    __tablename__ = 'branches'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    manager_name = db.Column(db.String(100))
    opening_time = db.Column(db.String(10), default='09:00')
    closing_time = db.Column(db.String(10), default='18:00')
    working_days = db.Column(db.String(100), default='Mon,Tue,Wed,Thu,Fri')
    is_main = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    organization = db.relationship('Organization', backref='branches')

    def __repr__(self):
        return f'<Branch {self.name}>'


# ─── ONBOARDING TRACKING ──────────────────────────────────────────────────────

class OnboardingProgress(db.Model):
    __tablename__ = 'onboarding_progress'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, unique=True)
    step_org_profile = db.Column(db.Boolean, default=False)
    step_branch = db.Column(db.Boolean, default=False)
    step_doctors = db.Column(db.Boolean, default=False)
    step_services = db.Column(db.Boolean, default=False)
    step_schedule = db.Column(db.Boolean, default=False)
    step_billing = db.Column(db.Boolean, default=False)
    step_staff = db.Column(db.Boolean, default=False)
    step_reminders = db.Column(db.Boolean, default=False)
    is_complete = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    organization = db.relationship('Organization', backref='onboarding', uselist=False)

    @property
    def completion_pct(self):
        steps = [self.step_org_profile, self.step_branch, self.step_doctors,
                 self.step_services, self.step_schedule, self.step_billing,
                 self.step_staff, self.step_reminders]
        done = sum(1 for s in steps if s)
        return int(done / len(steps) * 100)

    def __repr__(self):
        return f'<Onboarding org={self.org_id} {self.completion_pct}%>'


# ─── RBAC MODELS ──────────────────────────────────────────────────────────────

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)  # null = system role
    name = db.Column(db.String(50), nullable=False)
    label = db.Column(db.String(100))
    description = db.Column(db.Text)
    is_system = db.Column(db.Boolean, default=False)  # built-in roles
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    permissions = db.relationship('RolePermission', backref='role', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Role {self.name}>'


class Permission(db.Model):
    __tablename__ = 'permissions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)  # e.g. patients.view
    module = db.Column(db.String(50))
    action = db.Column(db.String(50))  # view, create, edit, delete
    label = db.Column(db.String(200))

    def __repr__(self):
        return f'<Permission {self.name}>'


class RolePermission(db.Model):
    __tablename__ = 'role_permissions'
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id'), nullable=False)

    permission = db.relationship('Permission')


class UserRole(db.Model):
    __tablename__ = 'user_roles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)

    role = db.relationship('Role')
    branch = db.relationship('Branch')


# ─── NOTIFICATION & REMINDER ENGINE ──────────────────────────────────────────

class NotificationTemplate(db.Model):
    __tablename__ = 'notification_templates'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    # event_type: appointment_reminder, follow_up_due, bill_due, welcome, result_ready, no_show
    channel = db.Column(db.String(20), default='sms')  # sms, whatsapp, email, push
    subject = db.Column(db.String(200))
    body = db.Column(db.Text, nullable=False)
    # Placeholders: {{patient_name}}, {{doctor_name}}, {{appointment_date}}, {{amount}}
    is_active = db.Column(db.Boolean, default=True)
    send_before_hours = db.Column(db.Integer, default=24)  # for appointment reminders
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    organization = db.relationship('Organization', backref='notification_templates')

    def __repr__(self):
        return f'<NotificationTemplate {self.name}>'


class NotificationLog(db.Model):
    __tablename__ = 'notification_logs'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    template_id = db.Column(db.Integer, db.ForeignKey('notification_templates.id'), nullable=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    event_type = db.Column(db.String(50))
    channel = db.Column(db.String(20))
    recipient = db.Column(db.String(200))  # phone/email
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='sent')  # sent, failed, pending, delivered
    error_message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship('Patient', backref='notification_logs')

    def __repr__(self):
        return f'<NotificationLog {self.event_type} → {self.recipient}>'


class ScheduledReminder(db.Model):
    __tablename__ = 'scheduled_reminders'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=True)
    reminder_type = db.Column(db.String(50))  # appointment, follow_up, bill, medication
    channel = db.Column(db.String(20), default='sms')
    recipient_phone = db.Column(db.String(30))
    recipient_email = db.Column(db.String(120))
    message = db.Column(db.Text)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    sent_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')  # pending, sent, failed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship('Patient', backref='reminders')
    appointment = db.relationship('Appointment', backref='reminders')

    def __repr__(self):
        return f'<ScheduledReminder {self.reminder_type} @{self.scheduled_at}>'


# ─── AI MODELS ────────────────────────────────────────────────────────────────

class AIInsight(db.Model):
    """Stores generated AI insights (business summaries, alerts, etc.)"""
    __tablename__ = 'ai_insights'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    insight_type = db.Column(db.String(50), nullable=False)
    # types: daily_summary, revenue_alert, no_show_alert, follow_up_alert,
    #        patient_risk, low_stock_alert, doctor_performance
    title = db.Column(db.String(300))
    content = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), default='info')  # info, warning, critical
    is_read = db.Column(db.Boolean, default=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    valid_until = db.Column(db.DateTime)
    metadata_json = db.Column(db.Text)  # JSON blob for extra data

    organization = db.relationship('Organization', backref='ai_insights')

    @property
    def extra_data(self):
        try:
            return json.loads(self.metadata_json) if self.metadata_json else {}
        except Exception:
            return {}

    def __repr__(self):
        return f'<AIInsight {self.insight_type}>'


class AIRiskScore(db.Model):
    """Patient-level risk scores computed by AI."""
    __tablename__ = 'ai_risk_scores'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    score_type = db.Column(db.String(50), nullable=False)
    # types: no_show, churn, readmission, chronic_deterioration
    score = db.Column(db.Float, nullable=False)   # 0.0 – 1.0
    risk_level = db.Column(db.String(20))          # low, medium, high, critical
    reason = db.Column(db.Text)
    recommended_action = db.Column(db.Text)
    computed_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)

    patient = db.relationship('Patient', backref='risk_scores')

    def __repr__(self):
        return f'<AIRiskScore patient={self.patient_id} {self.score_type}={self.score:.2f}>'


class FollowUpTask(db.Model):
    """AI-generated or manual follow-up tasks for patients."""
    __tablename__ = 'follow_up_tasks'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    source = db.Column(db.String(20), default='manual')  # manual, ai, medical_record
    priority = db.Column(db.String(20), default='normal')  # low, normal, high, urgent
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, done, cancelled
    completed_at = db.Column(db.DateTime)
    reminder_sent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship('Patient', backref='follow_up_tasks')
    doctor = db.relationship('Doctor', backref='follow_up_tasks')
    assignee = db.relationship('User', backref='follow_up_tasks')

    def __repr__(self):
        return f'<FollowUpTask {self.title} [{self.status}]>'


class AIUsageLog(db.Model):
    """Track AI feature usage per org for metering."""
    __tablename__ = 'ai_usage_logs'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    feature = db.Column(db.String(100))  # visit_summary, business_summary, risk_score, etc.
    tokens_used = db.Column(db.Integer, default=0)
    latency_ms = db.Column(db.Integer)
    status = db.Column(db.String(20), default='success')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<AIUsageLog {self.feature}>'


# ─── TENANT USAGE METERING ────────────────────────────────────────────────────

class TenantUsageMetric(db.Model):
    """Monthly usage snapshot per org for plan enforcement."""
    __tablename__ = 'tenant_usage_metrics'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    month = db.Column(db.String(7), nullable=False)  # YYYY-MM
    active_users = db.Column(db.Integer, default=0)
    active_branches = db.Column(db.Integer, default=0)
    patients_registered = db.Column(db.Integer, default=0)
    appointments_booked = db.Column(db.Integer, default=0)
    ai_calls = db.Column(db.Integer, default=0)
    reminders_sent = db.Column(db.Integer, default=0)
    bills_generated = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = db.relationship('Organization', backref='usage_metrics')

    def __repr__(self):
        return f'<TenantUsage org={self.org_id} {self.month}>'


# ─── PLATFORM ADMIN / SAAS BUSINESS ──────────────────────────────────────────

class PlatformAlert(db.Model):
    """Alerts for the MediOS platform admin team."""
    __tablename__ = 'platform_alerts'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    alert_type = db.Column(db.String(50))
    # types: trial_expiring, payment_failed, churn_risk, usage_spike, support_request
    message = db.Column(db.Text)
    severity = db.Column(db.String(20), default='info')  # info, warning, critical
    is_resolved = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    organization = db.relationship('Organization', backref='platform_alerts')

    def __repr__(self):
        return f'<PlatformAlert {self.alert_type}>'


class ServiceCatalog(db.Model):
    """Clinic/hospital services with pricing (configurable per tenant)."""
    __tablename__ = 'service_catalog'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(50))
    category = db.Column(db.String(100))  # consultation, procedure, lab, package
    description = db.Column(db.Text)
    price = db.Column(db.Float, default=0.0)
    duration_minutes = db.Column(db.Integer, default=30)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ServiceCatalog {self.name}>'


class DoctorSchedule(db.Model):
    """Doctor availability schedule per branch/day."""
    __tablename__ = 'doctor_schedules'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    day_of_week = db.Column(db.String(10), nullable=False)  # Mon, Tue, Wed...
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    slot_duration = db.Column(db.Integer, default=15)  # minutes
    max_patients = db.Column(db.Integer, default=20)
    is_active = db.Column(db.Boolean, default=True)

    doctor = db.relationship('Doctor', backref='schedules')

    def __repr__(self):
        return f'<DoctorSchedule Dr.{self.doctor_id} {self.day_of_week}>'
