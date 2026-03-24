"""
Migration script — adds all new columns and tables to existing SQLite database.
Run once: python migrate.py
"""
from app import create_app
from models import db

app = create_app()

# Columns to add: (table_name, column_name, column_def)
NEW_COLUMNS = [
    # patients
    ('patients',           'org_id',    'INTEGER REFERENCES organizations(id)'),
    ('patients',           'branch_id', 'INTEGER REFERENCES branches(id)'),
    # doctors
    ('doctors',            'org_id',    'INTEGER REFERENCES organizations(id)'),
    ('doctors',            'branch_id', 'INTEGER REFERENCES branches(id)'),
    # departments
    ('departments',        'org_id',    'INTEGER REFERENCES organizations(id)'),
    ('departments',        'branch_id', 'INTEGER REFERENCES branches(id)'),
    # appointments
    ('appointments',       'org_id',    'INTEGER REFERENCES organizations(id)'),
    ('appointments',       'branch_id', 'INTEGER REFERENCES branches(id)'),
    # medical_records
    ('medical_records',    'org_id',    'INTEGER REFERENCES organizations(id)'),
    ('medical_records',    'branch_id', 'INTEGER REFERENCES branches(id)'),
    # prescriptions
    ('prescriptions',      'org_id',    'INTEGER REFERENCES organizations(id)'),
    # lab_tests
    ('lab_tests',          'org_id',    'INTEGER REFERENCES organizations(id)'),
    # wards
    ('wards',              'org_id',    'INTEGER REFERENCES organizations(id)'),
    ('wards',              'branch_id', 'INTEGER REFERENCES branches(id)'),
    # beds
    ('beds',               'org_id',    'INTEGER REFERENCES organizations(id)'),
    # admissions
    ('admissions',         'org_id',    'INTEGER REFERENCES organizations(id)'),
    ('admissions',         'branch_id', 'INTEGER REFERENCES branches(id)'),
    # medicines
    ('medicines',          'org_id',    'INTEGER REFERENCES organizations(id)'),
    ('medicines',          'branch_id', 'INTEGER REFERENCES branches(id)'),
    # bills
    ('bills',              'org_id',    'INTEGER REFERENCES organizations(id)'),
    ('bills',              'branch_id', 'INTEGER REFERENCES branches(id)'),
    # staff
    ('staff',              'org_id',    'INTEGER REFERENCES organizations(id)'),
    ('staff',              'branch_id', 'INTEGER REFERENCES branches(id)'),
    # opd_queue
    ('opd_queue',          'org_id',    'INTEGER REFERENCES organizations(id)'),
    ('opd_queue',          'branch_id', 'INTEGER REFERENCES branches(id)'),
    # blood_inventory
    ('blood_inventory',    'org_id',    'INTEGER REFERENCES organizations(id)'),
    ('blood_inventory',    'branch_id', 'INTEGER REFERENCES branches(id)'),
    # blood_requests
    ('blood_requests',     'org_id',    'INTEGER REFERENCES organizations(id)'),
    # ambulances
    ('ambulances',         'org_id',    'INTEGER REFERENCES organizations(id)'),
    # ambulance_dispatches
    ('ambulance_dispatches', 'org_id',  'INTEGER REFERENCES organizations(id)'),
    # referrals
    ('referrals',          'org_id',    'INTEGER REFERENCES organizations(id)'),
    # lab_test_catalog
    ('lab_test_catalog',   'org_id',    'INTEGER REFERENCES organizations(id)'),
    # suppliers
    ('suppliers',          'org_id',    'INTEGER REFERENCES organizations(id)'),
    # purchase_orders
    ('purchase_orders',    'org_id',    'INTEGER REFERENCES organizations(id)'),
    ('purchase_orders',    'branch_id', 'INTEGER REFERENCES branches(id)'),
]

# New tables are created via db.create_all() below (PharmacySale, PharmacySaleItem)

with app.app_context():
    conn = db.engine.raw_connection()
    cursor = conn.cursor()

    added = 0
    skipped = 0

    for table, col, col_def in NEW_COLUMNS:
        try:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN {col} {col_def}')
            print(f'  ✅ Added {table}.{col}')
            added += 1
        except Exception as e:
            if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                skipped += 1
            else:
                print(f'  ⚠️  {table}.{col}: {e}')

    conn.commit()
    conn.close()

    print(f'\nColumns: {added} added, {skipped} already existed.')

    # Create all new tables (branches, onboarding_progress, roles, etc.)
    print('\nCreating new tables...')
    db.create_all()
    print('✅ All new tables created.')
    print('\nMigration complete!')
