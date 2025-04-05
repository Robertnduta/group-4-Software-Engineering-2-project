from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    hospital = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    profile_picture = db.Column(db.String(100))
    is_verified = db.Column(db.Boolean, default=False)
    role = db.Column(db.String(50), nullable=False, default="doctor")

    def __repr__(self):
        return f"<User {self.first_name} {self.last_name}>"

class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    visit_type = db.Column(db.String(50), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    patient_id = db.Column(db.string(20), db.ForeignKey('patient.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False)

    doctor = db.relationship('User', backref=db.backref('visits', lazy=True))
    patient = db.relationship('Patient', backref=db.backref('visits', lazy=True))

    def __repr__(self):
        return f"<Visit {self.visit_type} by Doctor {self.doctor_id}>"

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    patient_id = db.Column(db.string(20), db.ForeignKey('patient.id'), nullable=False)
    visit_id = db.Column(db.Integer, db.ForeignKey('visit.id'), nullable=False)

    patient = db.relationship('Patient', backref='payments', lazy=True)
    visit = db.relationship('Visit', backref='payments', lazy=True)

    def __repr__(self):
        return f"<Payment {self.amount} for Patient {self.patient_id} during Visit {self.visit_id}>"

class Radiology(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(100), nullable=False)
    test_type = db.Column(db.String(100), nullable=False)
    test_results = db.Column(db.String(500))
    date = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)

    def __repr__(self):
        return f"<Radiology Test {self.test_type} for {self.patient_name}>"

class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    patient_name = db.Column(db.String(100), nullable=False)
    medication_name = db.Column(db.String(200), nullable=False)
    dosage = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)

    doctor = db.relationship('User', backref=db.backref('prescriptions', lazy=True))

    def __repr__(self):
        return f"<Prescription for {self.patient_name} by Doctor {self.doctor_id}>"

class MedicalRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(100), nullable=False)
    record_type = db.Column(db.String(100), nullable=False)
    details = db.Column(db.String(500))
    date = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)

    def __repr__(self):
        return f"<MedicalRecord for {self.patient_name} - {self.record_type}>"

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    patient_name = db.Column(db.String(100), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)

    doctor = db.relationship('User', backref=db.backref('appointments', lazy=True))

    def __repr__(self):
        return f"<Appointment for {self.patient_name} with Doctor {self.doctor_id}>"

class Triage(db.Model):
    __tablename__ = 'triage'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.string(20), db.ForeignKey('patient.id'), nullable=False, index=True)
    patient = db.relationship('Patient', backref=db.backref('triage', lazy=True, cascade="all, delete-orphan"))
    temperature = db.Column(db.Float, nullable=True)
    blood_pressure = db.Column(db.String(20), nullable=True)
    heart_rate = db.Column(db.Integer, nullable=True)
    respiratory_rate = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Float, nullable=True)  # cm
    weight = db.Column(db.Float, nullable=True)  # kg
    oxygen_saturation = db.Column(db.Float, nullable=True)
    blood_sugar = db.Column(db.Float, nullable=True)  # mmol/L
    bmi = db.Column(db.Float, nullable=True)  # Calculated automatically
    triage_notes = db.Column(db.Text, nullable=True)
    triage_time = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def calculate_bmi(self):
        """Calculate and update BMI if height and weight are available."""
        if self.height and self.weight:
            self.bmi = round(self.weight / ((self.height / 100) ** 2), 2)

    def check_abnormalities(self):
        """Return a dictionary of abnormal vital signs."""
        abnormalities = {}
        if self.temperature and (self.temperature < 36.1 or self.temperature > 37.2):
            abnormalities['temperature'] = "Abnormal"
        if self.blood_pressure:
            systolic, diastolic = map(int, self.blood_pressure.split('/'))
            if systolic > 140 or diastolic > 90:
                abnormalities['blood_pressure'] = "High"
            elif systolic < 90 or diastolic < 60:
                abnormalities['blood_pressure'] = "Low"
        if self.heart_rate and (self.heart_rate < 60 or self.heart_rate > 100):
            abnormalities['heart_rate'] = "Abnormal"
        if self.respiratory_rate and (self.respiratory_rate < 12 or self.respiratory_rate > 20):
            abnormalities['respiratory_rate'] = "Abnormal"
        if self.oxygen_saturation and self.oxygen_saturation < 95:
            abnormalities['oxygen_saturation'] = "Low"
        if self.blood_sugar and (self.blood_sugar < 4.0 or self.blood_sugar > 7.8):
            abnormalities['blood_sugar'] = "Abnormal"
        return abnormalities

    def __repr__(self):
        return f"<Triage {self.patient.first_name} {self.patient.last_name} - {self.triage_time}>"

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(20), unique=True, nullable=False)  # Unique Patient ID
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    residency = db.Column(db.String(255), nullable=False)
    spouse_name = db.Column(db.String(100))
    spouse_phone = db.Column(db.String(15))
    next_of_kin = db.Column(db.String(100), nullable=False)
    registered_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # User who registered
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    def __repr__(self):
        return f"<Patient {self.first_name} {self.last_name}>"

class OPVisit(db.Model):
    __tablename__ = 'op_visits'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.string(20), db.ForeignKey('patient.id'), nullable=False, index=True)
    patient = db.relationship('Patient', backref=db.backref('op_visits', lazy=True, cascade="all, delete-orphan"))
    visit_purpose = db.Column(db.String(100), nullable=False)
    visit_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    bill = db.Column(db.Integer, default=50)  # Standard OP visit bill
    paid = db.Column(db.Boolean, default=False)  # Payment status
    status = db.Column(db.String(50), default="Pending", index=True)  # Pending, Completed, Cancelled

    def is_paid(self):
        """Check if the OP visit is fully paid."""
        return self.paid

    def __repr__(self):
        return f"<OPVisit {self.patient.first_name} {self.patient.last_name} - {self.visit_purpose} ({self.status})>"


class Bill(db.Model):
    __tablename__ = 'bills'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    patient_id = db.Column(db.string(20), db.ForeignKey('patient.id'), nullable=False)
    op_visit_id = db.Column(db.Integer, db.ForeignKey('op_visits.id'), nullable=False)

    service = db.Column(db.String(100), nullable=False)  # Service name (e.g., Registration, Triage, Lab Test)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending')  # Pending, Paid, Waived
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # When bill was added
    settled_at = db.Column(db.DateTime, nullable=True)  # When bill was settled

    # Relationships
    patient = db.relationship('Patient', backref='bills', lazy=True)
    op_visit = db.relationship('OPVisit', backref='bills', lazy=True)

    def mark_as_paid(self):
        """Mark bill as paid and set settled timestamp."""
        self.status = 'Paid'
        self.settled_at = datetime.utcnow()
        db.session.commit()

    def mark_as_waived(self):
        """Mark bill as waived (e.g., if patient is exempt)."""
        self.status = 'Waived'
        self.settled_at = datetime.utcnow()
        db.session.commit()

    @staticmethod
    def get_recent_settled_bills():
        """Retrieve bills settled within the last 48 hours."""
        cutoff_time = datetime.utcnow() - timedelta(hours=48)
        return Bill.query.filter(Bill.status == 'Paid', Bill.settled_at >= cutoff_time).all()

    @staticmethod
    def get_unsettled_bills(patient_id):
        """Retrieve all pending bills for a patient."""
        return Bill.query.filter(Bill.patient_id == patient_id, Bill.status == 'Pending').all()

    def __repr__(self):
        return f"<Bill {self.service} - {self.amount} KES for Patient {self.patient_id} ({self.status})>"