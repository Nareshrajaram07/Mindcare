from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "hello" 

socketio = SocketIO(app, cors_allowed_origins="*")

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",      # Change if not local
        user="root",           # Your MySQL username
        password="G1234512345",  # Your MySQL password
        database="arogyam",
    )

# Home Page
@app.route("/")
def home():
    return render_template("1main.html")

# Debug: Check if tables exist
@app.route("/debug/check-tables")
def debug_check_tables():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check prescriptions table
        cursor.execute("""
            SELECT COUNT(*) as count FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = 'arogyam' AND TABLE_NAME = 'prescriptions'
        """)
        prescriptions_exists = cursor.fetchone()['count'] > 0
        
        # Check prescription_medicines table
        cursor.execute("""
            SELECT COUNT(*) as count FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = 'arogyam' AND TABLE_NAME = 'prescription_medicines'
        """)
        medicines_exists = cursor.fetchone()['count'] > 0
        
        # Count prescriptions
        if prescriptions_exists:
            cursor.execute("SELECT COUNT(*) as count FROM prescriptions")
            prescription_count = cursor.fetchone()['count']
        else:
            prescription_count = "table doesn't exist"
        
        cursor.close()
        conn.close()
        
        return {
            "prescriptions_table_exists": prescriptions_exists,
            "prescription_medicines_table_exists": medicines_exists,
            "total_prescriptions": prescription_count
        }
    except Exception as e:
        return {"error": str(e)}

# Doctor Consultation Page
@app.route("/doctor")
def doctor_consultation():
    return render_template("2dp.html")

# AI Consultation Page (optional)
@app.route("/ai")
def ai_consultation():
    return "<h1>AI Consultation Page Coming Soon</h1>"

@app.route("/loginpatient", methods=["GET"])
def login_patient():
    return render_template("pl.html")

def get_specialists():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT specialization, 
               COUNT(*) AS count, 
               MIN(fees) AS min_fee, 
               MAX(fees) AS max_fee, 
               GROUP_CONCAT(DISTINCT available_days) AS days, 
               MIN(time_start) AS earliest_start, 
               MAX(time_end) AS latest_end
        FROM doctors
        GROUP BY specialization
    """)
    specialists = cursor.fetchall()
    cursor.close()
    conn.close()
    return specialists

# 🔹 Patient Dashboard Route
@app.route("/patient_dashboard")
def patient_dashboard():
    specialists = get_specialists()
    return render_template("mainpatientpage.html", specialists=specialists)

# 🔹 Patient Signup
@app.route("/submit", methods=["GET", "POST"])
def submit():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        phone = request.form.get("phone")
        age = request.form.get("age")

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if email already exists
            cursor.execute("SELECT * FROM patients WHERE email = %s", (email,))
            if cursor.fetchone():
                flash("You are already registered. Please log in.", "warning")
                return redirect(url_for("login_patient"))

            # Insert new patient
            cursor.execute(
                "INSERT INTO patients (name, email, password, phone, age) VALUES (%s, %s, %s, %s, %s)",
                (name, email, password, phone, age)
            )
            conn.commit()
            cursor.close()
            conn.close()

            flash("Registration successful! Welcome to your dashboard.", "success")
            return redirect(url_for("patient_dashboard"))

        except Exception as e:
            flash(f"Error: {e}", "danger")
            return redirect(url_for("login_patient"))

    return render_template("mainpatientpage.html")

# Login Page for registered patients
@app.route("/login")
def login_patient_registered():
    return render_template("pal.html")

@app.route("/pl")
def pl():
    return render_template("pl.html")

@app.route("/pmain", methods=["GET", "POST"])
def check_details():
    if request.method == "POST":
        name = request.form.get("name")
        password = request.form.get("password")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM patients WHERE name = %s AND password = %s", (name, password))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user:
            session["patient_id"] = user["id"]
            return redirect(url_for("patient_dashboard"))
        else:
            return render_template("pl.html", error="Invalid name or password. Please sign up.")

@app.route("/specialist/<specialization>")
def show_specialist(specialization):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Convert back the formatted specialization
    specialization = specialization.replace("_", " ").title()

    cursor.execute("""
        SELECT id, name, specialization, fees, available_days, time_start, time_end
        FROM doctors
        WHERE LOWER(specialization) = %s
    """, (specialization.lower(),))
    doctors = cursor.fetchall()

    cursor.close()
    conn.close()

    patient_id = session.get("patient_id")

    return render_template(
        "specialist_doctors.html",
        specialization=specialization,
        doctors=doctors,
        patient_id=patient_id
    )

@app.route("/logindoctor")
def dl():
    return render_template("dl.html")

@app.route("/doctor_login")
def dal():
    return render_template("dal.html")

@app.route("/doctor_dashboard")
def doctordashboard():
    license_number = request.args.get("license")
    if not license_number:
        flash("You must log in first", "danger")
        return redirect(url_for("dl"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get doctor details using license_number
    cursor.execute("SELECT * FROM doctors WHERE license_number = %s", (license_number,))
    doctor = cursor.fetchone()

    if not doctor:
        flash("Doctor not found", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for("dl"))

    # Get all patients who have chatted with this doctor
    cursor.execute("""
        SELECT DISTINCT 
            p.id as patient_id,
            p.name as patient_name,
            p.email as patient_email,
            p.phone as patient_phone,
            p.age as patient_age,
            MAX(c.timestamp) as last_message_time,
            COUNT(c.id) as total_messages,
            (SELECT c2.message 
             FROM chats c2 
             WHERE c2.patient_id = p.id AND c2.doctor_id = %s 
             ORDER BY c2.timestamp DESC 
             LIMIT 1) as last_message,
            (SELECT c3.sender 
             FROM chats c3 
             WHERE c3.patient_id = p.id AND c3.doctor_id = %s 
             ORDER BY c3.timestamp DESC 
             LIMIT 1) as last_sender
        FROM patients p
        INNER JOIN chats c ON p.id = c.patient_id
        WHERE c.doctor_id = %s
        GROUP BY p.id, p.name, p.email, p.phone, p.age
        ORDER BY MAX(c.timestamp) DESC
    """, (doctor['id'], doctor['id'], doctor['id']))
    
    patients_with_chats = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("doctordashboard.html", doctor=doctor, patients=patients_with_chats)

@app.route("/doctor_signup", methods=["GET", "POST"])
def doctor_signup():
    if request.method == "POST":
        name = request.form.get("doctor_name")
        specialization = request.form.get("specialist_type")
        license_number = request.form.get("license")
        fees = request.form.get("fees")
        available_days = ",".join(request.form.getlist("days"))
        time_start = request.form.get("time_start")
        time_end = request.form.get("time_end")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("doctor_signup"))

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if doctor already exists
            cursor.execute("SELECT * FROM doctors WHERE license_number = %s", (license_number,))
            if cursor.fetchone():
                flash("Doctor already registered. Please log in.", "warning")
                cursor.close()
                conn.close()
                return redirect(url_for("doctor_signup"))

            # Insert new doctor with all fields
            cursor.execute("""
                INSERT INTO doctors 
                (name, specialization, license_number, password, fees, available_days, time_start, time_end)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (name, specialization, license_number, password, fees, available_days, time_start, time_end))

            conn.commit()
            cursor.close()
            conn.close()

            flash("Doctor registration successful! Redirecting to dashboard...", "success")
            return redirect(url_for("doctordashboard", license=license_number))

        except Exception as e:
            flash(f"Error: {e}", "danger")
            return redirect(url_for("doctor_signup"))

    return render_template("dl.html")

@app.route("/doctor_login", methods=["GET", "POST"])
def doctor_login():
    if request.method == "POST":
        doctor_name = request.form.get("doctor_name")
        password = request.form.get("password")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if the doctor exists
        cursor.execute(
            "SELECT * FROM doctors WHERE name = %s AND password = %s",
            (doctor_name, password)
        )
        doctor = cursor.fetchone()

        cursor.close()
        conn.close()

        if doctor:
            # Store doctor info in session for better management
            session['doctor_id'] = doctor['id']
            session['doctor_name'] = doctor['name']
            session['doctor_license'] = doctor['license_number']
            
            flash(f"Welcome Dr. {doctor['name']}!", "success")
            return redirect(url_for("doctordashboard", license=doctor['license_number']))
        else:
            flash("Invalid username or password", "danger")
            return redirect(url_for("doctor_login"))

    return render_template("dal.html")

# EXISTING CHAT ROUTE (for Patient to Doctor - keep as is)
@app.route("/chat/<int:doctor_id>/<int:patient_id>")
def chat(doctor_id, patient_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM doctors WHERE id = %s", (doctor_id,))
    doctor = cursor.fetchone()

    # check payment status
    cursor.execute("""
        SELECT status FROM payments 
        WHERE doctor_id=%s AND patient_id=%s
        ORDER BY payment_date DESC LIMIT 1
    """, (doctor_id, patient_id))
    payment = cursor.fetchone()

    is_paid = payment and payment["status"] == "paid"

    cursor.close()
    conn.close()

    if not doctor:
        return "Doctor not found", 404

    return render_template("chat_doctor.html", doctor=doctor, is_paid=is_paid, patient_id=patient_id)

@app.route("/pay/<int:doctor_id>/<int:patient_id>", methods=["POST"])
def pay(doctor_id, patient_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO payments (doctor_id, patient_id, status)
        VALUES (%s, %s, 'paid')
    """, (doctor_id, patient_id))
    conn.commit()

    cursor.close()
    conn.close()

    flash("Payment successful! You can now start your consultation.", "success")
    return redirect(url_for("chat", doctor_id=doctor_id, patient_id=patient_id))

# UPDATED SEND MESSAGE ROUTE (handles both patient and doctor messages)
@app.route("/send_message", methods=["POST"])
def send_message():
    try:
        data = request.json
        patient_id = data.get("patient_id")
        doctor_id = data.get("doctor_id")
        sender = data.get("sender")   # 'patient' or 'doctor'
        message = data.get("message")

        if not all([patient_id, doctor_id, sender, message]):
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO chats (patient_id, doctor_id, sender, message, timestamp) VALUES (%s, %s, %s, %s, %s)",
            (patient_id, doctor_id, sender, message, datetime.now())
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "timestamp": datetime.now().strftime('%H:%M')
        })
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# UPDATED GET MESSAGES ROUTE (works for both patient and doctor chats)
@app.route("/get_messages/<int:doctor_id>/<int:patient_id>")
def get_messages(doctor_id, patient_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT sender, message, timestamp 
            FROM chats 
            WHERE doctor_id = %s AND patient_id = %s
            ORDER BY timestamp ASC
        """, (doctor_id, patient_id))
        messages = cursor.fetchall()

        # Format timestamps for JSON serialization
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                'sender': msg['sender'],
                'message': msg['message'],
                'timestamp': msg['timestamp'].strftime('%H:%M') if msg['timestamp'] else 'Now'
            })

        cursor.close()
        conn.close()
        
        return jsonify(formatted_messages)
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/chat_with_patient/<int:doctor_id>/<int:patient_id>')
def chat_with_patient(doctor_id, patient_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get doctor information
        cursor.execute("SELECT * FROM doctors WHERE id = %s", (doctor_id,))
        doctor = cursor.fetchone()
        
        if not doctor:
            flash('Doctor not found.', 'error')
            return redirect(url_for('dl'))
        
        # Get patient information
        cursor.execute("SELECT * FROM patients WHERE id = %s", (patient_id,))
        patient_data = cursor.fetchone()
        
        if not patient_data:
            flash('Patient not found.', 'error')
            return redirect(url_for('doctordashboard', license=doctor['license_number']))
        
        # Get all messages for this conversation
        cursor.execute("""
            SELECT sender, message, timestamp 
            FROM chats 
            WHERE doctor_id = %s AND patient_id = %s
            ORDER BY timestamp ASC
        """, (doctor_id, patient_id))
        
        messages = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Format patient data for template - CORRECTED STRUCTURE
        patient = {
            'patient_id': patient_data['id'],  # Make sure this matches your template
            'patient_name': patient_data['name'],
            'patient_age': patient_data['age'],
            'patient_phone': patient_data.get('phone', ''),
            'patient_email': patient_data.get('email', ''),
            'last_message_time': messages[-1]['timestamp'].strftime('%Y-%m-%d %H:%M') if messages else 'Never'
        }
        
        # Convert messages to the format expected by template
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                'sender': msg['sender'],
                'message': msg['message'],  # Changed from 'content' to 'message'
                'timestamp': msg['timestamp']
            })
        
        return render_template('chat_with_patient.html', 
                             doctor=doctor, 
                             patient=patient, 
                             messages=formatted_messages)
                             
    except Exception as e:
        print(f"Error in chat_with_patient route: {str(e)}")  # Add logging
        flash(f'Error loading chat: {str(e)}', 'error')
        return redirect(url_for('doctordashboard'))
    
@app.route('/give_prescription/<int:doctor_id>/<int:patient_id>')
def give_prescription(doctor_id, patient_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get doctor information
        cursor.execute("SELECT * FROM doctors WHERE id = %s", (doctor_id,))
        doctor = cursor.fetchone()
        
        if not doctor:
            flash('Doctor not found.', 'error')
            return redirect(url_for('dl'))
        
        # Get patient information
        cursor.execute("SELECT * FROM patients WHERE id = %s", (patient_id,))
        patient_data = cursor.fetchone()
        
        if not patient_data:
            flash('Patient not found.', 'error')
            return redirect(url_for('doctordashboard', license=doctor['license_number']))
        
        cursor.close()
        conn.close()
        
        # Format patient data
        patient = {
            'patient_id': patient_data['id'],
            'patient_name': patient_data['name'],
            'patient_age': patient_data['age'],
            'patient_phone': patient_data.get('phone', ''),
            'patient_email': patient_data.get('email', '')
        }
        
        return render_template('prescription.html', doctor=doctor, patient=patient)
                             
    except Exception as e:
        print(f"Error in give_prescription route: {str(e)}")
        flash(f'Error loading prescription page: {str(e)}', 'error')
        return redirect(url_for('doctordashboard'))

# Save prescription from doctor form
@app.route('/save_prescription', methods=['POST'])
def save_prescription():
    try:
        data = request.json
        doctor_id = data.get('doctor_id')
        patient_id = data.get('patient_id')
        diagnosis = data.get('diagnosis')
        medicines = data.get('medicines', [])
        notes = data.get('notes', '')

        if not all([doctor_id, patient_id, diagnosis]):
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert prescription
        cursor.execute("""
            INSERT INTO prescriptions (doctor_id, patient_id, diagnosis, notes)
            VALUES (%s, %s, %s, %s)
        """, (doctor_id, patient_id, diagnosis, notes))
        
        prescription_id = cursor.lastrowid

        # Insert medicines for this prescription
        for medicine in medicines:
            cursor.execute("""
                INSERT INTO prescription_medicines 
                (prescription_id, medicine_name, dosage, duration, instructions)
                VALUES (%s, %s, %s, %s, %s)
            """, (prescription_id, medicine['name'], medicine['dosage'], 
                  medicine['duration'], medicine.get('instructions', '')))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "Prescription saved successfully",
            "prescription_id": prescription_id
        })

    except Exception as e:
        print(f"Error saving prescription: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Get patient prescriptions
@app.route('/get_prescriptions/<int:patient_id>')
def get_prescriptions(patient_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get all prescriptions for this patient
        cursor.execute("""
            SELECT p.id, p.doctor_id, p.diagnosis, p.notes, p.created_date,
                   d.name as doctor_name, d.specialization
            FROM prescriptions p
            JOIN doctors d ON p.doctor_id = d.id
            WHERE p.patient_id = %s
            ORDER BY p.created_date DESC
        """, (patient_id,))
        
        prescriptions = cursor.fetchall()

        # Get medicines for each prescription
        for prescription in prescriptions:
            cursor.execute("""
                SELECT medicine_name, dosage, duration, instructions
                FROM prescription_medicines
                WHERE prescription_id = %s
            """, (prescription['id'],))
            prescription['medicines'] = cursor.fetchall()
            # Format date
            prescription['created_date'] = prescription['created_date'].strftime('%Y-%m-%d %H:%M')

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "prescriptions": prescriptions
        })

    except Exception as e:
        print(f"Error getting prescriptions: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# View prescriptions page for patient
@app.route('/view_prescriptions/<int:doctor_id>/<int:patient_id>')
def view_prescriptions(doctor_id, patient_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get doctor info
        cursor.execute("SELECT * FROM doctors WHERE id = %s", (doctor_id,))
        doctor = cursor.fetchone()

        # Get patient info
        cursor.execute("SELECT * FROM patients WHERE id = %s", (patient_id,))
        patient_data = cursor.fetchone()

        # Get all prescriptions for this patient from this doctor
        cursor.execute("""
            SELECT p.id, p.diagnosis, p.notes, p.created_date,
                   d.name as doctor_name, d.specialization
            FROM prescriptions p
            JOIN doctors d ON p.doctor_id = d.id
            WHERE p.patient_id = %s AND p.doctor_id = %s
            ORDER BY p.created_date DESC
        """, (patient_id, doctor_id))
        
        prescriptions = cursor.fetchall()

        # Get medicines for each prescription
        for prescription in prescriptions:
            cursor.execute("""
                SELECT medicine_name, dosage, duration, instructions
                FROM prescription_medicines
                WHERE prescription_id = %s
            """, (prescription['id'],))
            prescription['medicines'] = cursor.fetchall()
            # Format date properly
            if prescription['created_date']:
                prescription['created_date'] = prescription['created_date'].strftime('%Y-%m-%d %H:%M:%S')
            print(f"DEBUG view_prescriptions - Prescription {prescription['id']}: {prescription}")

        print(f"DEBUG view_prescriptions - Total prescriptions: {len(prescriptions)}")

        cursor.close()
        conn.close()

        return render_template('view_prescriptions.html', 
                             doctor=doctor,
                             patient=patient_data,
                             prescriptions=prescriptions)

    except Exception as e:
        import traceback
        print(f"Error in view_prescriptions: {str(e)}")
        traceback.print_exc()
        flash(f'Error loading prescriptions: {str(e)}', 'error')
        return redirect(url_for('chat', doctor_id=doctor_id, patient_id=patient_id))
# ---------------------------
# Video Call Signaling Events
# ---------------------------

@socketio.on('join_room')
def handle_join(data):
    room = f"{data['doctor_id']}_{data['patient_id']}"
    join_room(room)
    emit('room_joined', {'room': room}, room=room)

@socketio.on('start_call')
def handle_start_call(data):
    room = f"{data['doctor_id']}_{data['patient_id']}"
    emit('incoming_call', {'from': data['user_type']}, room=room, include_self=False)

@socketio.on('webrtc_offer')
def handle_offer(data):
    emit('webrtc_offer', data, room=data['room'], include_self=False)

@socketio.on('webrtc_answer')
def handle_answer(data):
    emit('webrtc_answer', data, room=data['room'], include_self=False)

@socketio.on('webrtc_ice_candidate')
def handle_ice_candidate(data):
    emit('webrtc_ice_candidate', data, room=data['room'], include_self=False)
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')
    
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000) 