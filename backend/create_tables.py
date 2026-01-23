import mysql.connector

# Connect to MySQL
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="G1234512345",
    database="arogyam"
)

cursor = conn.cursor()

# Create prescriptions table
prescription_table = """
CREATE TABLE IF NOT EXISTS prescriptions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id INT NOT NULL,
    patient_id INT NOT NULL,
    diagnosis TEXT NOT NULL,
    notes TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id),
    FOREIGN KEY (patient_id) REFERENCES patients(id)
);
"""

# Create prescription_medicines table
medicines_table = """
CREATE TABLE IF NOT EXISTS prescription_medicines (
    id INT AUTO_INCREMENT PRIMARY KEY,
    prescription_id INT NOT NULL,
    medicine_name VARCHAR(255) NOT NULL,
    dosage VARCHAR(100) NOT NULL,
    duration VARCHAR(100) NOT NULL,
    instructions VARCHAR(255),
    FOREIGN KEY (prescription_id) REFERENCES prescriptions(id) ON DELETE CASCADE
);
"""

try:
    cursor.execute(prescription_table)
    print("✓ Prescriptions table created successfully")
    
    cursor.execute(medicines_table)
    print("✓ Prescription medicines table created successfully")
    
    conn.commit()
    print("\n✓ All tables created successfully!")
except Exception as e:
    print(f"✗ Error creating tables: {e}")
finally:
    cursor.close()
    conn.close()
