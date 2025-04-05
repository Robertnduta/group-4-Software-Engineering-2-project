from flask import Flask, render_template, request, redirect, flash, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from openpyxl import Workbook
import os
import logging

from sqlalchemy import create_engine, text
app = Flask(__name__)

# Initialize SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:4013@127.0.0.1/medflow'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
app = Flask(__name__)

# Secret key for secure sessions
app.secret_key = os.urandom(24)

# Configure the PostgreSQL connection
DATABASE_URL = 'postgresql://postgres:4013@127.0.0.1/medflow'
engine = create_engine(DATABASE_URL)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Home page route (index.html) which is the login page
@app.route('/')
def index():
    return render_template('index.html')

# Registration Route for Doctors using raw SQL
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get form data
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        age = request.form.get('age')
        hospital = request.form.get('hospital')
        department = request.form.get('department')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        profile_picture = request.files.get('profile_picture')

        # Validate passwords match
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('register'))

        # Hash the password
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        # Handle profile picture upload
        profile_picture_filename = None
        if profile_picture and profile_picture.filename:
            profile_picture_filename = profile_picture.filename
            profile_picture.save(os.path.join(app.config['UPLOAD_FOLDER'], profile_picture_filename))

        # Insert new doctor into the database using raw SQL
        try:
            # Note: "user" is a reserved keyword in PostgreSQL, so we enclose it in double quotes.
            insert_query = text("""
                INSERT INTO "user" (first_name, last_name, email, phone, age, hospital, department, password, profile_picture, is_verified, role)
                VALUES (:first_name, :last_name, :email, :phone, :age, :hospital, :department, :password, :profile_picture, :is_verified, :role)
            """)
            params = {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "age": age,
                "hospital": hospital,
                "department": department,
                "password": hashed_password,
                "profile_picture": profile_picture_filename,
                "is_verified": False,  # Needs admin verification
                "role": "doctor"
            }
            with engine.connect() as connection:
                connection.execute(insert_query, params)
                connection.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
            return redirect(url_for('register'))

    return render_template('registration.html')

# Login Route using raw SQL with proper row conversion
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Use a raw SQL query to fetch the user record.
        query = text('SELECT * FROM "user" WHERE email = :email')
        with engine.connect() as connection:
            result = connection.execute(query, {"email": email})
            row = result.fetchone()
            # Convert using _mapping to get a dictionary.
            user = dict(row._mapping) if row is not None else None

        if not user:
            flash("No account found with this email.", "danger")
            return redirect(url_for('login'))

        if not check_password_hash(user['password'], password):
            flash("Incorrect password. Try again.", "danger")
            return redirect(url_for('login'))

        session['user_id'] = user['id']
        session['user_name'] = user['first_name']
        flash("Login successful!", "success")
        return redirect(url_for('dashboard'))

    return render_template('index.html')

# Logout Route
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for('login'))


# Forgot Password Route
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        with engine.connect() as connection:
            query = text('SELECT * FROM "user" WHERE email = :email')
            result = connection.execute(query, {"email": email})
            user = result.fetchone()

        if user:
            flash("A password reset link has been sent to your email.", "success")
        else:
            flash("Email not found.", "danger")
        return redirect(url_for('forgot_password'))
    
    return render_template('forgot_password.html')

# Custom error handler for 404
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


# Dashboard Route
@app.route('/dashboard')
def dashboard():
    with engine.connect() as connection:
        total_patients = connection.execute(text('SELECT count(*) FROM "user"')).scalar()
        total_op_visits = connection.execute(text("SELECT count(*) FROM visit WHERE visit_type = 'OP Visit'")).scalar()
        total_inpatients = connection.execute(text("SELECT count(*) FROM visit WHERE visit_type = 'Inpatient'")).scalar()
        total_doctors = connection.execute(text('SELECT count(*) FROM "user" WHERE role = :role'), {"role": "doctor"}).scalar()
        total_revenue = connection.execute(text("SELECT sum(amount) FROM payment")).scalar() or 0

    return render_template('dashboard.html', 
                           totalOp=total_op_visits, 
                           totalInpatients=total_inpatients, 
                           totalDoctors=total_doctors, 
                           totalRevenue=total_revenue)

@app.route('/api/dashboard-data', methods=['GET'])
def dashboard_data():
    """
    Fetch dashboard statistics from the database.
    Returns:
        JSON response with:
         - totalPatients: count from the patient table.
         - totalOPVisits: count of OP visits from op_visits table (where visit_purpose is 'OP Visit').
         - totalInpatients: count of inpatient visits from op_visits table (where visit_purpose is 'Inpatient').
         - totalDoctors: count of doctors from the "user" table (where role is 'doctor').
         - totalRevenue: total revenue from the payment table.
    """
    try:
        with engine.connect() as connection:
            # Total patients from patient table
            total_patients = connection.execute(
                text('SELECT count(*) FROM patient')
            ).scalar()

            # Total OP visits: based on visit_purpose
            total_op_visits = connection.execute(
                text("SELECT count(*) FROM op_visits WHERE visit_purpose = 'OP Visit'")
            ).scalar()

            # Total Inpatient visits: based on visit_purpose
            total_inpatients = connection.execute(
                text("SELECT count(*) FROM op_visits WHERE visit_purpose = 'Inpatient'")
            ).scalar()

            # Total doctors from "user" table (note: "user" is a reserved word in PostgreSQL)
            total_doctors = connection.execute(
                text('SELECT count(*) FROM "user" WHERE role = :role'),
                {"role": "doctor"}
            ).scalar()

            # Total revenue from payment table (using COALESCE to default to 0)
            total_revenue = connection.execute(
                text("SELECT coalesce(sum(amount), 0) FROM payment")
            ).scalar()

        data = {
            "totalPatients": total_patients,
            "totalOPVisits": total_op_visits,
            "totalInpatients": total_inpatients,
            "totalDoctors": total_doctors,
            "totalRevenue": total_revenue
        }
        return jsonify(data), 200

    except Exception as e:
        # Log error details in a real-world application
        return jsonify({"error": str(e)}), 500


  # Route to handle bill settlement
@app.route('/settle_bill', methods=['POST'])
def settle_bill():
    patient_id = request.form['patient_id']
    bill = Bill.query.filter_by(patient_id=patient_id, status='Pending').first()
    with app.app_context():
        db.session.commit()
    if not bill:
        flash("No pending bill found!", "danger")
        return redirect(url_for('cashier'))

    bill.status = "Paid"
    db.session.commit()

    patient = Patient.query.get(patient_id)

    # Check if the bill is only for OP visit
    if bill.amount == 50:
        return redirect(url_for('triage'))
    else:
        return redirect(url_for('dashboard'))

def generate_patient_id():
    """
    Generates the next unique patient ID in the format MF2025-000000011.
    Queries the database for the latest ID and increments it.
    """
    with engine.connect() as connection:
        result = connection.execute(text("SELECT patient_id FROM patient ORDER BY patient_id DESC LIMIT 1"))
        row = result.fetchone()

        if row:
            latest_patient_id = row._mapping['patient_id']
            try:
                parts = latest_patient_id.split("-")
                number = int(parts[1])  # Extract patient number
            except ValueError:
                number = 10  # Default to 11 if parsing fails
            next_patient_number = number + 1
        else:
            next_patient_number = 11  # Start from 11 if no records exist

    current_year = datetime.now().year
    while True:
        unique_id = f"MF{current_year}-{str(next_patient_number).zfill(9)}"  # Ensures 9-digit numbering
        with engine.connect() as connection:
            existing_patient = connection.execute(text("SELECT patient_id FROM patient WHERE patient_id = :pid"), {"pid": unique_id}).fetchone()
            if not existing_patient:
                return unique_id
        next_patient_number += 1  # Increment and retry if ID exists

@app.route('/patient_registration', methods=['GET', 'POST'])
def patient_registration():
    if 'user_id' not in session:
        flash("You must be logged in to register a patient.", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Extract form data
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        age = request.form.get('age')
        gender = request.form.get('gender')
        phone = request.form.get('phone')
        residency = request.form.get('residency')
        spouse_name = request.form.get('spouse_name')
        spouse_phone = request.form.get('spouse_phone')
        next_of_kin = request.form.get('next_of_kin')
        registered_by = session['user_id']  # User ID of the logged-in registrar

        # Generate a unique Patient ID
        unique_id = generate_patient_id()

        # Insert the new patient record
        try:
            with engine.begin() as connection:
                insert_patient_query = text("""
                    INSERT INTO patient (patient_id, first_name, last_name, age, gender, phone, residency, 
                                         spouse_name, spouse_phone, next_of_kin, registered_by, registration_date)
                    VALUES (:patient_id, :first_name, :last_name, :age, :gender, :phone, :residency, 
                            :spouse_name, :spouse_phone, :next_of_kin, :registered_by, NOW())
                """)
                connection.execute(insert_patient_query, {
                    "patient_id": unique_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "age": age,
                    "gender": gender,
                    "phone": phone,
                    "residency": residency,
                    "spouse_name": spouse_name,
                    "spouse_phone": spouse_phone,
                    "next_of_kin": next_of_kin,
                    "registered_by": registered_by
                })

            # Create a Bill for the patient registration with a default service value "Registration Fee"
            with engine.begin() as connection:
                insert_bill_query = text("""
                    INSERT INTO bills (patient_id, service, amount, status, created_at)
                    VALUES (:patient_id, :service, :amount, :status, NOW())
                """)
                connection.execute(insert_bill_query, {
                    "patient_id": unique_id,
                    "service": "Registration Fee",
                    "amount": 100,
                    "status": "Unpaid"
                })

            flash(f"Patient {first_name} {last_name} registered successfully! ID: {unique_id}", "success")
            return redirect(url_for('create_op_visit'))

        except IntegrityError:
            flash("A patient with this ID already exists. Please try again.", "danger")
            return redirect(url_for('patient_registration'))
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
            return redirect(url_for('patient_registration'))

    else:  # GET request: Generate a unique ID for display
        unique_id = generate_patient_id()
        return render_template('patient_registration.html', unique_id=unique_id)






@app.route('/create_op_visit', methods=['GET', 'POST'])
def create_op_visit():
    if request.method == 'POST':
        patient_id = request.form.get('patient_id')
        visit_purpose = request.form.get('visit_purpose')
        bill_amount = 50  # Fixed OP Visit charge

        try:
            with engine.begin() as connection:
                # Ensure patient exists
                query = text("SELECT * FROM patient WHERE patient_id = :patient_id")
                patient = connection.execute(query, {"patient_id": patient_id}).fetchone()

                if not patient:
                    flash("Patient not found.", "danger")
                    return redirect(url_for('create_op_visit'))

                # Check if patient already has an OP visit within the last 48 hours
                existing_visit_query = text("""
                    SELECT 1 FROM op_visits 
                    WHERE patient_id = :patient_id AND visit_date >= NOW() - INTERVAL '48 HOURS'
                """)
                existing_visit = connection.execute(existing_visit_query, {"patient_id": patient_id}).fetchone()

                if existing_visit:
                    flash("OP Visit already exists for this patient within 48 hours.", "warning")
                    return redirect(url_for('create_op_visit'))

                # Insert OP Visit and return the new ID
                op_visit_query = text("""
                    INSERT INTO op_visits (patient_id, visit_purpose, visit_date, bill, paid, status)
                    VALUES (:patient_id, :visit_purpose, NOW(), :bill, FALSE, 'Pending')
                """)
                connection.execute(op_visit_query, {
                    "patient_id": patient_id,
                    "visit_purpose": visit_purpose,
                    "bill": bill_amount
                })

            flash('OP Visit created successfully!', 'success')
            return redirect(url_for('triage'))

        except Exception as e:
            logging.error(f"Error in create_op_visit: {str(e)}")
            flash(f"Database Error: {str(e)}", "danger")
            return redirect(url_for('create_op_visit'))

    else:
        # Fetch recent patients (last 48 hours) without OP visit
        forty_eight_hours_ago = datetime.utcnow() - timedelta(hours=48)
        with engine.connect() as connection:
            recent_patients_query = text("""
                SELECT patient_id, first_name, last_name FROM patient
                WHERE registration_date >= :forty_eight_hours_ago
                AND patient_id NOT IN (
                    SELECT patient_id FROM op_visits WHERE visit_date >= :forty_eight_hours_ago
                )
            """)
            recent_patients = connection.execute(recent_patients_query, {
                "forty_eight_hours_ago": forty_eight_hours_ago
            }).mappings().all()

        medical_purposes = [
            "General Consultation", "Emergency Care", "Maternity", "ICU", "Radiology",
            "Laboratory Tests", "Pharmacy", "Surgery", "Dialysis", "Mental Health",
            "Cardiology", "Orthopedics", "ENT", "Dermatology", "Gastroenterology",
            "Neurology", "Oncology", "Pediatrics", "Geriatrics", "Physiotherapy"
        ]

        return render_template(
            'create_op_visit.html',
            recent_patients=recent_patients,
            visit_purposes=medical_purposes
        )




@app.route('/cancel_op_visit/<int:visit_id>', methods=['POST'])
def cancel_op_visit(visit_id):
    op_visit = OPVisit.query.get_or_404(visit_id)

    # Remove bill related to this visit
    Bill.query.filter_by(patient_id=op_visit.patient_id, status="Pending").delete()

    # Remove the OP visit
    db.session.delete(op_visit)
    db.session.commit()

    flash('OP Visit cancelled successfully!', 'warning')
    return redirect(url_for('create_op_visit'))


@app.route('/api/recent-billed-patients', methods=['GET'])
def get_recent_billed_patients():
    patients = db.session.query(Patient).join(Bill).filter(Bill.status == 'Pending').order_by(Bill.id.desc()).limit(10).all()
    
    return jsonify([
        {'id': p.id, 'first_name': p.first_name, 'last_name': p.last_name}
        for p in patients
    ])
    
    
    
    
    
@app.route('/triage', methods=['GET', 'POST'])
def triage():
    if 'user_id' not in session:
        flash("You must be logged in to access triage.", "danger")
        return redirect(url_for('login'))

    with engine.connect() as connection:
        # Fetch all patients in op_visits
        all_patients_query = text("""
            SELECT op.id AS visit_id, op.patient_id, p.first_name, p.last_name, p.age, p.gender, op.visit_purpose, op.visit_date
            FROM op_visits op
            JOIN patient p ON op.patient_id = p.patient_id
            ORDER BY op.visit_date DESC
        """)
        patients_result = connection.execute(all_patients_query)
        all_patients = [dict(row._mapping) for row in patients_result.fetchall()]

        # Fetch all doctors
        doctors_query = text("""
            SELECT id, first_name, last_name, department FROM "user" WHERE role = 'doctor'
        """)
        doctors_result = connection.execute(doctors_query)
        all_doctors = [dict(row._mapping) for row in doctors_result.fetchall()]

    if request.method == 'POST':
        if 'cancel_visit' in request.form:
            visit_id = request.form.get('visit_id')

            try:
                with engine.begin() as connection:
                    # Delete the visit from op_visits
                    connection.execute(text("DELETE FROM op_visits WHERE id = :visit_id"), {"visit_id": visit_id})
                    
                    # Delete any associated bills
                    connection.execute(text("DELETE FROM billing WHERE visit_id = :visit_id"), {"visit_id": visit_id})

                flash("Visit successfully cancelled!", "success")
            except Exception as e:
                flash(f"Error: {str(e)}", "danger")

            return redirect(url_for('triage'))

        elif 'triage_submit' in request.form:
            try:
                patient_id = request.form['patient_id']
                doctor_id = request.form['doctor_id']
                room = request.form['room']
                temperature = float(request.form['temperature'])
                blood_pressure = request.form['blood_pressure']
                heart_rate = int(request.form['heart_rate'])
                respiratory_rate = int(request.form['respiratory_rate'])
                height = float(request.form['height']) / 100  # Convert cm to meters
                weight = float(request.form['weight'])
                oxygen_saturation = float(request.form['oxygen_saturation'])
                blood_sugar = float(request.form['blood_sugar'])
                triage_notes = request.form['triage_notes']

                # Calculate BMI
                bmi = round(weight / (height ** 2), 2)

                # BMI check: alert if the BMI falls outside a reasonable range for height/weight
                if height < 1.2 or height > 2.5:
                    flash("Height seems unrealistic. Please check the value.", "warning")
                elif weight < 30 or weight > 200:
                    flash("Weight seems unrealistic. Please check the value.", "warning")

                if bmi < 18.5:
                    bmi_category = "Underweight"
                elif 18.5 <= bmi <= 24.9:
                    bmi_category = "Normal weight"
                elif 25 <= bmi <= 29.9:
                    bmi_category = "Overweight"
                else:
                    bmi_category = "Obese"

                # Display BMI category to user
                flash(f"Calculated BMI: {bmi} - Category: {bmi_category}", "info")

                with engine.begin() as connection:
                    # Insert into triage table
                    connection.execute(text("""
                        INSERT INTO triage (
                            patient_id, doctor_id, room, temperature, blood_pressure, heart_rate, 
                            respiratory_rate, height, weight, bmi, oxygen_saturation, blood_sugar, 
                            triage_notes, triage_time
                        ) VALUES (
                            :patient_id, :doctor_id, :room, :temperature, :blood_pressure, :heart_rate, 
                            :respiratory_rate, :height, :weight, :bmi, :oxygen_saturation, :blood_sugar, 
                            :triage_notes, NOW()
                        )
                    """), {
                        "patient_id": patient_id,
                        "doctor_id": doctor_id,
                        "room": room,
                        "temperature": temperature,
                        "blood_pressure": blood_pressure,
                        "heart_rate": heart_rate,
                        "respiratory_rate": respiratory_rate,
                        "height": height,
                        "weight": weight,
                        "bmi": bmi,
                        "oxygen_saturation": oxygen_saturation,
                        "blood_sugar": blood_sugar,
                        "triage_notes": triage_notes
                    })

                    # Delete the patient from op_visits table after triage
                    connection.execute(text("DELETE FROM op_visits WHERE patient_id = :patient_id"), {"patient_id": patient_id})

                flash("Triage successfully recorded and patient removed from OP Visit!", "success")
                return redirect(url_for('consultation'))  # Redirect to consultation page

            except Exception as e:
                flash(f"Error: {str(e)}", "danger")

            return redirect(url_for('triage'))

    return render_template('triage.html', patients=all_patients, doctors=all_doctors)








@app.route('/consultation', methods=['GET', 'POST'])
def consultation():
    if 'user_id' not in session:
        flash("You must be logged in to access consultation.", "danger")
        return redirect(url_for('login'))

    doctor_id = session['user_id']  # Assuming the doctor's user_id is stored in the session

    if request.method == 'POST':
        patient_id = request.form['patient_id']
        doctor_notes = request.form['doctor_notes']
        prescription = request.form['prescription']
        service = request.form['service']
        amount = float(request.form['amount'])
        referral = request.form['referral']

        # Insert Consultation Data
        try:
            with engine.connect() as connection:
                # Insert into consultations
                connection.execute(text("""
                    INSERT INTO consultations (patient_id, doctor_id, doctor_notes, prescription, referral)
                    VALUES (:patient_id, :doctor_id, :doctor_notes, :prescription, :referral)
                """), {
                    'patient_id': patient_id,
                    'doctor_id': doctor_id,
                    'doctor_notes': doctor_notes,
                    'prescription': prescription,
                    'referral': referral
                })

                # Insert into bills (billing service)
                connection.execute(text("""
                    INSERT INTO bills (patient_id, service, amount, status, created_at)
                    VALUES (:patient_id, :service, :amount, 'Pending', :created_at)
                """), {
                    'patient_id': patient_id,
                    'service': service,
                    'amount': amount,
                    'created_at': datetime.now()
                })
            
            flash("Consultation saved successfully!", "success")
            return redirect(url_for('consultation'))  # Redirect to the consultation page

        except Exception as e:
            flash(f"Error: {str(e)}", "danger")

    # Fetch patients from triage table (with patient_id) and join with the patient table
    with engine.connect() as connection:
        patients_query = text("""
            SELECT 
                p.patient_id, 
                p.first_name, 
                p.last_name, 
                p.age, 
                p.gender, 
                p.phone, 
                p.residency, 
                p.spouse_name, 
                p.spouse_phone, 
                p.next_of_kin, 
                t.triage_time
            FROM triage t
            JOIN patient p ON t.patient_id = p.patient_id
            WHERE t.doctor_id IS NULL  -- Only show patients without a doctor assigned
        """)
        patients_result = connection.execute(patients_query)
        patients = [dict(row._mapping) for row in patients_result.fetchall()]

    return render_template('consultation.html', patients=patients)


@app.route('/save-consultation', methods=['POST'])
def save_consultation():
    data = request.form
    patient_id = data['patient_id']
    doctor_notes = data['doctor_notes']
    prescription = data['prescription']
    referral = data['referral']
    service = data['service']
    amount = data['amount']

    # Insert consultation details into the database
    try:
        with engine.connect() as connection:
            # Insert into consultations
            result = connection.execute(text("""
                INSERT INTO public.consultations (patient_id, doctor_notes, prescription, referral, billing_id)
                VALUES (:patient_id, :doctor_notes, :prescription, :referral, :billing_id) RETURNING id;
            """), {
                'patient_id': patient_id,
                'doctor_notes': doctor_notes,
                'prescription': prescription,
                'referral': referral,
                'billing_id': None  # You can update this later if needed
            })
            
            consultation_id = result.fetchone()[0]  # Get the consultation id

            # Insert billing details
            connection.execute(text("""
                INSERT INTO public.bills (patient_id, service, amount, status)
                VALUES (:patient_id, :service, :amount, 'Pending');
            """), {
                'patient_id': patient_id,
                'service': service,
                'amount': amount
            })
        
        return jsonify({"message": "Consultation saved successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route('/print_notes/<consultation_id>')
def print_notes(consultation_id):
    # Fetch the consultation data from the database
    with engine.connect() as connection:
        consultation = connection.execute(text("""
            SELECT doctor_notes, doctor_id FROM consultations WHERE id = :id
        """), {'id': consultation_id}).fetchone()

    # Generate HTML for the printable note
    html = render_template('doctor_notes_printable.html', consultation=consultation)

    # Convert HTML to PDF
    pdf = pdfkit.from_string(html, False)

    # Return PDF as a response
    return Response(pdf, content_type='application/pdf')


@app.route('/download_bill/<bill_id>')
def download_bill(bill_id):
    with engine.connect() as connection:
        bill = connection.execute(text("""
            SELECT service, amount FROM bills WHERE id = :id
        """), {'id': bill_id}).fetchone()

    wb = Workbook()
    ws = wb.active
    ws.append(['Service', 'Amount'])
    ws.append([bill['service'], bill['amount']])

    file_path = f"bill_{bill_id}.xlsx"
    wb.save(file_path)

    return send_file(file_path, as_attachment=True)










@app.route('/radiology')
def radiology():
    return render_template('radiology.html')

@app.route('/inpatient')
def inpatient():
    return render_template('inpatient.html')

@app.route('/ward')
def ward():
    return render_template('ward.html')
@app.route('/cashier', methods=['GET'])
def cashier():
    try:
        with engine.connect() as connection:
            # Fetch all patients who have pending bills
            query = text("""
                SELECT DISTINCT p.id, p.first_name, p.last_name
                FROM patient p
                JOIN bills b ON p.id = b.patient_id
                WHERE b.status = 'Pending'
            """)
            result = connection.execute(query)
            patients = [{"id": row[0], "name": f"{row[1]} {row[2]}"} for row in result]

        return render_template('cashier.html', patients=patients)

    except Exception as e:
        print(f"An error occurred: {e}")
        return "Error retrieving bills", 500
    
    
@app.route('/api/bills/<patient_id>', methods=['GET'])
def get_bills(patient_id):
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, op_visit_id, service, amount, status, created_at, settled_at
                FROM bills 
                WHERE patient_id = :patient_id
            """), {"patient_id": patient_id})
            
            bills = [dict(row) for row in result]

        return jsonify({"success": True, "bills": bills})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})





@app.route('/pay_bill/<int:bill_id>', methods=['GET', 'POST'])
def pay_bill(bill_id):
    bill = Bill.query.get(bill_id)
    
    if not bill:
        flash('Bill not found!', 'danger')
        return redirect(url_for('cashier'))

    # Update the bill status to 'Paid'
    bill.status = 'Paid'
    db.session.commit()

    flash(f'Bill for {bill.patient.first_name} {bill.patient.last_name} paid successfully!', 'success')
    return redirect(url_for('cashier'))


@app.route('/search_patient', methods=['GET'])
def search_patient():
    search_query = request.args.get('search_query', '')
    patients = Patient.query.filter(
        (Patient.first_name.ilike(f'%{search_query}%')) | 
        (Patient.last_name.ilike(f'%{search_query}%')) |
        (Patient.id == search_query)
    ).all()
    
    return render_template('create_op_visit.html', patients=patients)

@app.errorhandler(500)
def internal_error(error):
    # Remove the db.session.rollback() line because db is no longer defined
    return render_template('500.html', error=error), 500

@app.errorhandler(Exception)
def handle_exception(error):
    print(f"An error occurred: {error}")
    return render_template('500.html'), 500

# Run migration
if __name__ == '__main__':
    from flask_migrate import upgrade, migrate, init

    # Ensure migrations are in place and the database schema is up-to-date
    with app.app_context():
        # Initialize the migration repository if it doesn't exist
        if not os.path.exists("migrations"):
            init()

        # Run migrations
        migrate()

        # Apply database migrations (this should handle your schema changes)
        upgrade()

    
    app.run(debug=True)

# Run the application
if __name__ == '__main__':
    app.run(debug=True)