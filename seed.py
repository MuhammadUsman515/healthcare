"""
Seed script to initialize the database with sample data.
Run: python seed.py
"""
from app import create_app
from models import db, User, Department, Doctor, Patient, Appointment, Medicine, Ward, Bed, Bill, BillItem
from datetime import datetime, date, timedelta
import random
import string


def generate_patient_id():
    return 'P' + ''.join(random.choices(string.digits, k=6))


def generate_appointment_id():
    return 'APT' + ''.join(random.choices(string.digits, k=6))


def generate_bill_number():
    return 'BILL' + ''.join(random.choices(string.digits, k=6))


def seed_database():
    app = create_app()
    with app.app_context():
        db.create_all()
        print("Database tables created.")

        # Check if already seeded
        if User.query.filter_by(username='admin').first():
            print("Database already seeded. Skipping...")
            return

        # ── Users ───────────────────────────────────────────────────────
        print("Creating users...")
        admin = User(username='admin', email='admin@medicare.com', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)

        reception_user = User(username='reception', email='reception@medicare.com', role='receptionist')
        reception_user.set_password('rec123')
        db.session.add(reception_user)

        nurse_user = User(username='nurse1', email='nurse1@medicare.com', role='nurse')
        nurse_user.set_password('nurse123')
        db.session.add(nurse_user)

        # Doctor users
        doctor_users = []
        for i, (first, last, uname) in enumerate([
            ('James', 'Smith', 'drsmith'),
            ('Sarah', 'Johnson', 'drjohnson'),
            ('Michael', 'Williams', 'drwilliams'),
            ('Emily', 'Brown', 'drbrown'),
            ('Robert', 'Davis', 'drdavis'),
            ('Jennifer', 'Miller', 'drmiller'),
            ('William', 'Wilson', 'drwilson'),
            ('Linda', 'Moore', 'drmoore'),
        ]):
            u = User(username=uname, email=f'{uname}@medicare.com', role='doctor')
            u.set_password('doctor123')
            db.session.add(u)
            doctor_users.append((u, first, last))

        db.session.flush()

        # ── Departments ─────────────────────────────────────────────────
        print("Creating departments...")
        depts_data = [
            ('Cardiology', 'Heart and cardiovascular system care'),
            ('Neurology', 'Brain and nervous system disorders'),
            ('Orthopedics', 'Musculoskeletal system and injuries'),
            ('Pediatrics', 'Medical care for children and adolescents'),
            ('Gynecology', 'Female reproductive system care'),
            ('Emergency Medicine', 'Acute and emergency medical care'),
            ('General Medicine', 'Primary and general healthcare'),
            ('Surgery', 'Surgical procedures and post-operative care'),
        ]
        departments = []
        for name, desc in depts_data:
            d = Department(name=name, description=desc)
            db.session.add(d)
            departments.append(d)
        db.session.flush()

        # ── Doctors ─────────────────────────────────────────────────────
        print("Creating doctors...")
        specializations = [
            'Cardiologist', 'Neurologist', 'Orthopedic Surgeon',
            'Pediatrician', 'Gynecologist', 'Emergency Physician',
            'General Practitioner', 'Surgeon'
        ]
        qualifications = [
            'MBBS, MD, DM Cardiology', 'MBBS, MD Neurology', 'MBBS, MS Orthopedics',
            'MBBS, MD Pediatrics', 'MBBS, MS Gynecology', 'MBBS, MD Emergency',
            'MBBS, MD General Medicine', 'MBBS, MS Surgery'
        ]
        doctors = []
        for i, (u, first, last) in enumerate(doctor_users):
            doc = Doctor(
                user_id=u.id,
                first_name=first,
                last_name=last,
                specialization=specializations[i % len(specializations)],
                department_id=departments[i % len(departments)].id,
                phone=f'+1-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}',
                email=u.email,
                license_number=f'LIC{random.randint(10000, 99999)}',
                qualification=qualifications[i % len(qualifications)],
                experience_years=random.randint(5, 25),
                consultation_fee=random.choice([100, 150, 200, 250, 300]),
                available_days='Mon,Tue,Wed,Thu,Fri',
                available_from='09:00',
                available_to='17:00',
            )
            db.session.add(doc)
            doctors.append(doc)
        db.session.flush()

        # Set department heads
        for i, dept in enumerate(departments):
            if i < len(doctors):
                dept.head_doctor_id = doctors[i].id
        db.session.flush()

        # ── Patients ─────────────────────────────────────────────────────
        print("Creating patients...")
        first_names = ['Alice', 'Bob', 'Carol', 'David', 'Eva', 'Frank', 'Grace', 'Henry',
                       'Iris', 'Jack', 'Karen', 'Leo', 'Maria', 'Noah', 'Olivia', 'Peter',
                       'Quinn', 'Rachel', 'Sam', 'Tina', 'Uma', 'Victor', 'Wendy', 'Xavier']
        last_names = ['Anderson', 'Baker', 'Clark', 'Davis', 'Evans', 'Fisher', 'Garcia',
                      'Harris', 'Ibrahim', 'Jones', 'King', 'Lewis', 'Martin', 'Nelson',
                      'Owen', 'Parker', 'Quinn', 'Roberts', 'Scott', 'Taylor']
        blood_groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
        genders = ['Male', 'Female']

        patients = []
        for i in range(30):
            first = first_names[i % len(first_names)]
            last = last_names[i % len(last_names)]
            dob = date(random.randint(1950, 2005), random.randint(1, 12), random.randint(1, 28))
            p = Patient(
                patient_id=generate_patient_id(),
                first_name=first,
                last_name=last,
                date_of_birth=dob,
                gender=random.choice(genders),
                blood_group=random.choice(blood_groups),
                phone=f'+1-555-{random.randint(100,999)}-{random.randint(1000,9999)}',
                email=f'{first.lower()}.{last.lower()}{i}@email.com',
                address=f'{random.randint(1,999)} Main St, City {i+1}',
                emergency_contact_name=f'Emergency Contact {i+1}',
                emergency_contact_phone=f'+1-555-{random.randint(100,999)}-{random.randint(1000,9999)}',
                emergency_contact_relation=random.choice(['Spouse', 'Parent', 'Sibling', 'Child']),
                allergies=random.choice([None, 'Penicillin', 'Aspirin', 'Latex', 'None known']),
                chronic_conditions=random.choice([None, 'Hypertension', 'Diabetes', 'Asthma', None, None]),
                insurance_provider=random.choice([None, 'BlueCross', 'Aetna', 'United Health', 'Cigna']),
                created_at=datetime.utcnow() - timedelta(days=random.randint(0, 180)),
            )
            db.session.add(p)
            patients.append(p)
        db.session.flush()

        # ── Appointments ─────────────────────────────────────────────────
        print("Creating appointments...")
        statuses = ['scheduled', 'completed', 'completed', 'completed', 'cancelled']
        times = ['09:00', '09:30', '10:00', '10:30', '11:00', '11:30', '14:00', '14:30', '15:00', '15:30', '16:00']

        appointments = []
        today = date.today()
        for i in range(60):
            apt_date = today + timedelta(days=random.randint(-30, 14))
            status = random.choice(statuses)
            if apt_date > today:
                status = 'scheduled'
            elif apt_date == today:
                status = random.choice(['scheduled', 'completed'])
            apt = Appointment(
                appointment_id=generate_appointment_id(),
                patient_id=random.choice(patients).id,
                doctor_id=random.choice(doctors).id,
                appointment_date=apt_date,
                appointment_time=random.choice(times),
                reason=random.choice([
                    'Regular checkup', 'Follow-up visit', 'Chest pain',
                    'Headache', 'Back pain', 'Fever', 'Diabetes management',
                    'Blood pressure check', 'Knee pain', 'Skin rash'
                ]),
                status=status,
                created_at=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
            )
            db.session.add(apt)
            appointments.append(apt)
        db.session.flush()

        # ── Medicines ─────────────────────────────────────────────────────
        print("Creating medicines...")
        medicines_data = [
            ('Amoxicillin', 'Amoxicillin', 'Antibiotic', 'PharmaCo', 'Capsule', 0.5, 500, 50),
            ('Paracetamol', 'Acetaminophen', 'Analgesic', 'MediPharm', 'Tablet', 0.1, 1000, 100),
            ('Ibuprofen', 'Ibuprofen', 'NSAID', 'HealthCorp', 'Tablet', 0.2, 800, 80),
            ('Metformin', 'Metformin HCl', 'Antidiabetic', 'DiabetCare', 'Tablet', 0.3, 600, 60),
            ('Amlodipine', 'Amlodipine Besylate', 'Antihypertensive', 'CardioMed', 'Tablet', 0.8, 400, 40),
            ('Omeprazole', 'Omeprazole', 'Antacid', 'GastroPharm', 'Capsule', 0.4, 300, 30),
            ('Atorvastatin', 'Atorvastatin Calcium', 'Statin', 'LipidCare', 'Tablet', 1.2, 250, 25),
            ('Ciprofloxacin', 'Ciprofloxacin HCl', 'Antibiotic', 'BacterioKill', 'Tablet', 0.9, 200, 20),
            ('Salbutamol', 'Albuterol', 'Bronchodilator', 'RespiCare', 'Inhaler', 8.5, 150, 15),
            ('Insulin Glargine', 'Insulin Glargine', 'Insulin', 'DiabetCare', 'Vial', 45.0, 100, 10),
            ('Aspirin', 'Acetylsalicylic Acid', 'Analgesic', 'MediPharm', 'Tablet', 0.05, 2000, 200),
            ('Lisinopril', 'Lisinopril', 'ACE Inhibitor', 'CardioMed', 'Tablet', 0.6, 350, 35),
            ('Prednisolone', 'Prednisolone', 'Corticosteroid', 'ImmunoPharm', 'Tablet', 0.7, 180, 18),
            ('Azithromycin', 'Azithromycin', 'Antibiotic', 'PharmaCo', 'Tablet', 1.5, 120, 12),
            ('Pantoprazole', 'Pantoprazole Sodium', 'Antacid', 'GastroPharm', 'Tablet', 0.9, 90, 9),
        ]
        for name, generic, cat, mfr, unit, price, stock, reorder in medicines_data:
            m = Medicine(
                name=name,
                generic_name=generic,
                category=cat,
                manufacturer=mfr,
                unit=unit,
                unit_price=price,
                stock_quantity=stock,
                reorder_level=reorder,
                expiry_date=date(2026, random.randint(1, 12), random.randint(1, 28)),
            )
            db.session.add(m)

        # ── Wards & Beds ─────────────────────────────────────────────────
        print("Creating wards and beds...")
        wards_data = [
            ('General Ward A', 'general', departments[6].id, 20, 150),
            ('General Ward B', 'general', departments[6].id, 20, 150),
            ('ICU', 'icu', departments[5].id, 10, 800),
            ('Cardiology Ward', 'private', departments[0].id, 10, 500),
            ('Pediatric Ward', 'general', departments[3].id, 15, 200),
            ('Private Suite', 'private', None, 5, 1000),
        ]
        for ward_name, ward_type, dept_id, num_beds, rate in wards_data:
            ward = Ward(name=ward_name, ward_type=ward_type, department_id=dept_id, total_beds=num_beds)
            db.session.add(ward)
            db.session.flush()
            for j in range(1, num_beds + 1):
                status = 'available'
                if j <= num_beds // 3:
                    status = 'occupied'
                bed = Bed(
                    bed_number=f'{ward_name[:3].upper()}-{j:02d}',
                    ward_id=ward.id,
                    status=status,
                    daily_rate=rate
                )
                db.session.add(bed)

        # ── Bills ─────────────────────────────────────────────────────────
        print("Creating sample bills...")
        for i in range(20):
            p = random.choice(patients)
            subtotal = random.uniform(100, 2000)
            tax = subtotal * 0.05
            discount = random.uniform(0, 50)
            total = subtotal + tax - discount
            paid = random.choice([0, total * 0.5, total])
            payment_status = 'paid' if paid >= total else ('partial' if paid > 0 else 'pending')

            bill = Bill(
                bill_number=generate_bill_number(),
                patient_id=p.id,
                due_date=date.today() + timedelta(days=30),
                subtotal=round(subtotal, 2),
                tax=round(tax, 2),
                discount=round(discount, 2),
                total_amount=round(total, 2),
                paid_amount=round(paid, 2),
                payment_status=payment_status,
                payment_method=random.choice(['cash', 'card', 'insurance']) if paid > 0 else None,
                bill_date=datetime.utcnow() - timedelta(days=random.randint(0, 60)),
            )
            db.session.add(bill)
            db.session.flush()

            # Add bill items
            items = [
                ('Consultation Fee', 'consultation', 1, 150),
                ('Lab Tests', 'lab', 2, 75),
                ('Medication', 'medicine', 3, 25),
            ]
            for desc, itype, qty, price in items[:random.randint(1, 3)]:
                item = BillItem(
                    bill_id=bill.id,
                    description=desc,
                    item_type=itype,
                    quantity=qty,
                    unit_price=price,
                    total_price=qty * price
                )
                db.session.add(item)

        db.session.commit()
        print("\n✓ Database seeded successfully!")
        print("\nLogin credentials:")
        print("  Admin:       admin / admin123")
        print("  Doctor:      drsmith / doctor123")
        print("  Nurse:       nurse1 / nurse123")
        print("  Receptionist: reception / rec123")
        print("\nRun: python app.py")


if __name__ == '__main__':
    seed_database()
