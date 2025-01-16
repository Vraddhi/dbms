from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash,session,jsonify
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import random
from PIL import Image
import pytesseract
import os
import re

app = Flask(__name__)
app.secret_key = 'your_secret_key'

client = MongoClient("mongodb://localhost:27017/")
db = client["DBMS_LAB"]
overtime_collection = db["teacher_overtime"]

#this is ocr thing
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


# Define time slots as per your requirements
time_slots = [
    {"slot_id": "A1", "start_time": "9:00 AM", "end_time": "10:00 AM"},
    {"slot_id": "A2", "start_time": "10:00 AM", "end_time": "11:00 AM"},
    {"slot_id": "A3", "start_time": "11:30 AM", "end_time": "12:30 PM"},
    {"slot_id": "A4", "start_time": "12:30 PM", "end_time": "1:30 PM"},
    {"slot_id": "A5", "start_time": "2:30 PM", "end_time": "3:30 PM"},
    {"slot_id": "A6", "start_time": "3:30 PM", "end_time": "4:30 PM"},
    {"slot_id": "B1", "start_time": "9:00 AM", "end_time": "11:00 AM"},
    {"slot_id": "B2", "start_time": "11:30 AM", "end_time": "1:30 PM"},
    {"slot_id": "B3", "start_time": "2:30 PM", "end_time": "4:30 PM"}
]

def assign_time_slots(courses, semester_group):
    timetable = []
    available_slots = time_slots[:]
    random.shuffle(available_slots)  # Randomize slots

    # Fetch already assigned slots for teachers across all semesters
    teacher_schedule = {}
    subject_daily_schedule = {}  # To track subjects per day

    existing_timetables = db.timetable.find({})
    
    for timetable_entry in existing_timetables:
        for course in timetable_entry['courses']:
            teacher_id = course['teacher_id']
            course_name = course['course_name']

            if teacher_id not in teacher_schedule:
                teacher_schedule[teacher_id] = set()

            if 'assigned_slots' in course:
                assigned_slot_ids = {slot['slot_id'] for slot in course['assigned_slots']}
                teacher_schedule[teacher_id].update(assigned_slot_ids)

            for slot in course.get('assigned_slots', []):
                day = slot['slot_id'][0]  # Extract day (A1 → A)
                if course_name not in subject_daily_schedule:
                    subject_daily_schedule[course_name] = set()
                subject_daily_schedule[course_name].add(day)

    for course in courses:
        course_hours = int(course['hours_per_week'])
        teacher_id = course['teacher_id']
        course_name = course['course_name']
        assigned_slots = []

        if teacher_id not in teacher_schedule:
            teacher_schedule[teacher_id] = set()
        if course_name not in subject_daily_schedule:
            subject_daily_schedule[course_name] = set()

        teacher_assigned_days = set()

        for _ in range(course_hours):
            random.shuffle(available_slots)  # Shuffle before each assignment
            selected_slot = None

            for slot in available_slots:
                day = slot['slot_id'][0]  # Extract day (A1 → A)

                if (slot['slot_id'] not in teacher_schedule[teacher_id]) and \
                   (day not in subject_daily_schedule[course_name]) and \
                   (day not in teacher_assigned_days):
                    selected_slot = slot
                    teacher_schedule[teacher_id].add(slot['slot_id'])
                    subject_daily_schedule[course_name].add(day)
                    teacher_assigned_days.add(day)
                    available_slots.remove(slot)
                    assigned_slots.append(slot)
                    break

            if not selected_slot:
                flash(f'Not enough valid slots for {course["faculty_name"]} ({course["course_name"]})', 'error')
                return None

        timetable.append({
            'course_name': course['course_name'],
            'faculty_name': course['faculty_name'],
            'teacher_id': course['teacher_id'],
            'assigned_slots': assigned_slots
        })

    return timetable

@app.route("/admin-dashboard")
def admin_dashboard():
    return render_template('admin-entry.html')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
# this is OCR
@app.route('/upload_timetable', methods=['POST'])
def upload_timetable():
    if 'timetable' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('ocr_timetable'))

    file = request.files['timetable']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('ocr_timetable'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            # OCR Processing
            text = pytesseract.image_to_string(Image.open(filepath))
            flash("OCR Text Extraction Successful.", "info")
            # Parse and insert timetable
            timetable_data = parse_timetable(text)
            if timetable_data and 'courses' in timetable_data:
                result = db.timetable.insert_one(timetable_data)
                flash(f"Timetable inserted successfully with ID {result.inserted_id}.", "success")
            else:
                flash("No valid timetable data extracted.", "error")
        except Exception as e:
            flash(f"Error during OCR processing: {e}", "error")
    else:
        flash("Invalid file format. Please upload an image file.", "error")

    return redirect(url_for('ocr_timetable'))

def parse_timetable(ocr_text):
    try:
        timetable = []

        # Patterns
        day_pattern = r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b"
        time_slot_pattern = r"\b(\d{1,2}:\d{2}\s*[-~]\s*\d{1,2}:\d{2})\b"
        course_code_pattern = r"\b[A-Z]+\d+[A-Z]+\b"

        # Split into lines
        lines = ocr_text.split("\n")
        current_day = None
        current_time_slots = []
        current_courses = []

        for line in lines:
            line = line.strip()
            if not line:
                continue  # Skip empty lines

            # Detect day
            day_match = re.search(day_pattern, line, re.IGNORECASE)
            if day_match:
                current_day = day_match.group().capitalize()
                print(f"Found Day: {current_day}")
                continue

            # Detect time slots
            time_slots = re.findall(time_slot_pattern, line)
            if time_slots:
                current_time_slots = time_slots
                print(f"Found Time Slots: {current_time_slots}")
                continue

            # Detect course codes
            course_codes = re.findall(course_code_pattern, line)
            if course_codes:
                if not current_time_slots:  # Handle missing time slots
                    current_time_slots = ["Unknown"] * len(course_codes)
                for course_code in course_codes:
                    # Match each course with the corresponding time slot
                    for time_slot in current_time_slots:
                        timetable.append({
                            'course_code': course_code.strip(),
                            'day': current_day if current_day else "Unknown",
                            'time_slot': time_slot.strip() if time_slot else "Unknown"
                        })
                print(f"Added Courses: {course_codes} for Day: {current_day or 'Unknown'}")

        return {'courses': timetable}
    except Exception as e:
        print(f"Error during OCR processing: {e}")
        return {'courses': []}
    
@app.route('/ocr')  # This will be the URL path
def ocr_page():
    return render_template('OCR.html')  # This looks for OCR.html in the 'templates' folder

@app.route('/personalized_timetable')
def personalized_timetable():
    # Get the course code from the query parameters
    course_code = request.args.get('course_code')
    
    if not course_code:
        return "Course code is missing", 400

    # Query the MongoDB collection for the timetable matching the course code
    timetable = list(timetable_collection.find({'course_code': course_code}))
    
    if not timetable:
        return "No timetable found for the provided course code.", 404
    
    # Pass the timetable data and course code to the template
    return render_template('personalized_timetable.html', timetable=timetable, course_code=course_code)

@app.route("/ocr_timetable", methods=['GET', 'POST'])
def ocr_timetable():
    if request.method == 'POST':
        if 'timetable' not in request.files:
            flash('No file part in the request', 'error')
            return redirect(url_for('ocr_timetable'))

        file = request.files['timetable']
        if file.filename == '':
            flash('No file selected for upload', 'error')
            return redirect(url_for('ocr_timetable'))

        if file and allowed_file(file.filename):
            try:
                # Save the uploaded file
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                # Perform OCR on the uploaded file
                text = pytesseract.image_to_string(Image.open(filepath))
                print("Extracted OCR Text:", text)

                # Parse OCR text into timetable data
                timetable_data = parse_timetable(text)
                print("Parsed Timetable Data:", timetable_data)

                # Insert timetable data into MongoDB
                if timetable_data and 'courses' in timetable_data:
                    result = db.timetable.insert_one(timetable_data)
                    print("Inserted Timetable ID:", result.inserted_id)
                    flash('Timetable uploaded and processed successfully!', 'success')
                else:
                    flash('Failed to extract meaningful timetable data.', 'error')

            except Exception as e:
                print("Error during OCR processing:", e)
                flash('An error occurred while processing the timetable.', 'error')
        else:
            flash('Invalid file type. Please upload a valid image file.', 'error')

        return redirect(url_for('ocr_timetable'))

    # Render the OCR upload page for GET requests
    return render_template('OCR.html')
# till here
@app.route('/check_teacher_ot')
@app.route('/generate_timetable', methods=['POST'])
def generate_timetable():
    data = request.json
    semester_type = data.get('semester_type')
    semester = data.get('semester')
    semester_group = data.get('semester_group')
    courses = data.get('courses')

    timetable = assign_time_slots(courses, semester_group)
    if timetable is None:
        return jsonify({"error": "Unable to assign time slots due to conflicts."}), 400
    
    for course in timetable:
        course.pop('semester_group', None)

    timetable_entry = {
        'semester_type': semester_type,
        'semester': semester,
        'semester_group': semester_group,
        'courses': timetable
    }
    db.timetable.insert_one(timetable_entry)

    return jsonify({"message": "Timetable generated successfully", "timetable": timetable}), 201

@app.route('/dummy')
def dummy():
    return render_template('dummy.html')

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        admin = db.admins.find_one({"email": email})

        if admin and password == admin['password']:
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin email or password', 'error')
            return redirect(url_for('admin_login'))
    return render_template('admin-login.html')

@app.route('/teacher-login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Find the user in the database
        user = db.users.find_one({"email": email})

        # Verify the password correctly
        if user and check_password_hash(user['password'], password):  # Compare hashed password correctly
            session["email"] = email  # Store email in session
            flash('Login successful', 'success')
            return redirect(url_for('dashboard'))  # Redirect to dashboard
        else:
            flash('Invalid email or password', 'error')
            return redirect(url_for('teacher_login'))  # Redirect to login page

    return render_template('teacher-login.html')

@app.route('/teacher-signup', methods=['GET', 'POST'])
def teacher_signup():
    if request.method == 'POST':
        # Get form data
        email = request.form['email'].strip().lower()
        password = request.form['password']
        faculty_id = request.form['faculty_id'].strip()
        name = request.form['name'].strip()
        department = request.form['department'].strip()
        roles = request.form['roles'].strip()

        try:
            # Check for duplicate user
            existing_user = db.users.find_one({"email": email})
            if existing_user:
                flash('A user with this email already exists. Please log in.', 'error')
                return redirect(url_for('teacher_login'))

            # Hash the password
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

            # Prepare data to insert into MongoDB
            user_data = {
                'email': email,
                'password': hashed_password,
                'faculty_id': faculty_id,
                'name': name,
                'department': department,
                'roles': roles
            }

            try:
                db.users.insert_one(user_data) 
                return redirect(url_for('teacher_login'))
            except:
                print(".")

        except Exception as e:
            print(f"Error during signup: {str(e)}")
            flash(f"An error occurred while creating your account: {str(e)}", 'error')
            return redirect(url_for('teacher_signup'))
    return render_template('teacher-signup.html')

@app.route('/dashboard')
def dashboard():
    return render_template('teacher-dashboard.html')

@app.route('/success')
def success():
    return "Operation successful!"

@app.route('/add_course', methods=['GET', 'POST'])
def add_course():
    if request.method == 'POST':
        semester = request.form.get('semester')
        course_id = request.form.get('course_id')
        course_name = request.form.get('course_name')
        course_type = request.form.get('course_type')

        existing_course = db.courses.find_one({
            "semester": semester,
            "course_id": course_id,
            "course_name": course_name,
            "course_type": course_type
        })
        if existing_course:
            flash("A course with the same details already exists!", "error")
            return redirect(url_for('add_course'))
        course_data = {
            "semester": semester,
            "course_id": course_id,
            "course_name": course_name,
            "course_type": course_type
        }

        db.courses.insert_one(course_data)
        flash(f"Course '{course_name}' added successfully!", "success")
        return redirect('/admin_dashboard')
    return render_template('courses.html')

@app.route("/")
def entry():
    return render_template('mainentry.html')

@app.route('/log_overtime', methods=['POST'])
def log_overtime():
    if 'email' not in session:
        return jsonify({"error": "Unauthorized"}), 401  # User must be logged in

    data = request.json
    date = data.get('date')
    start_time = data.get('startTime')
    end_time = data.get('endTime')
    description = data.get('description')
    email = session['email']  # Get logged-in faculty email

    if not date or not start_time or not end_time or not description:
        return jsonify({"error": "Missing required fields"}), 400

    start_datetime = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
    end_datetime = datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M")

    if end_datetime <= start_datetime:
        return jsonify({"error": "End time must be after start time"}), 400

    hours_worked = (end_datetime - start_datetime) / timedelta(hours=1)

    overtime_entry = {
        "email": email,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "hours_worked": hours_worked,
        "description": description
    }

    overtime_collection.insert_one(overtime_entry)  # Save to MongoDB

    return jsonify({"message": "Overtime logged successfully"})


@app.route('/get_overtime_events', methods=['GET'])
def get_overtime_events():
    if 'email' not in session:
        return jsonify({"error": "Unauthorized"}), 401  # User must be logged in

    email = session['email']
    date = request.args.get('date')

    # Query MongoDB for records matching faculty's email & selected date
    records = list(overtime_collection.find({"email": email, "date": date}, {"_id": 0}))

    return jsonify(records)
 
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('teacher_login'))

if __name__ == "__main__":
    app.run(debug=True)
