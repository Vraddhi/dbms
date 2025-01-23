from datetime import datetime

from bson import ObjectId
from flask import Flask, render_template, request, redirect, url_for, flash,session,jsonify
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import random
from PIL import Image
import pytesseract
import os
import re
from datetime import timedelta
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'

client = MongoClient("mongodb://localhost:27017/")
db = client["management_dbms"]
overtime_collection = db["teacher_overtime"]
timetable_collection=db['timetable']
users_collection = db["users"]

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

@app.route("/")
def entry():
    return render_template('mainentry.html')

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



@app.route('/dashboard')
def dashboard():
    return render_template('teacher-dashboard.html')


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

@app.route('/admin-view-OT', methods=['GET'])
def admin_view_ot():
    return render_template('admin-view-OT.html')

@app.route('/get_overtime', methods=['GET'])
def get_overtime():
    # Retrieve filters from the request
    search_query = request.args.get('search_query', '').strip()
    range_type = request.args.get('range', 'week')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    # Determine date range
    now = datetime.now()
    if range_type == 'week':
        start_date = now - timedelta(days=now.weekday())
        end_date = now
    elif range_type == 'month':
        start_date = now.replace(day=1)
        end_date = now
    elif range_type == 'custom' and start_date and end_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
    else:
        return jsonify({"error": "Invalid date range"}), 400

    # Create a base query for the overtime collection
    overtime_query = {"date": {"$gte": start_date.strftime('%Y-%m-%d'), "$lte": end_date.strftime('%Y-%m-%d')}}

    # Modify the query based on the search input
    if search_query:
        matching_users = list(db.users.find({
            "$or": [
                {"name": {"$regex": search_query, "$options": "i"}},
                {"faculty_id": search_query}
            ]
        }))
        user_emails = [user["email"] for user in matching_users]
        if user_emails:
            overtime_query["email"] = {"$in": user_emails}
        else:
            return jsonify([])  # No matches found

    # Aggregate overtime data
    pipeline = [
        {"$match": overtime_query},
        {
            "$group": {
                "_id": "$email",
                "total_hours": {"$sum": "$hours_worked"},
            }
        },
        {"$sort": {"_id": 1}},
        {"$limit": 10}
    ]

    overtime_data = list(overtime_collection.aggregate(pipeline))

    # Attach faculty names to the aggregated data
    result = []
    for data in overtime_data:
        user = db.users.find_one({"email": data["_id"]})
        if user:
            result.append({
                "faculty_name": user["name"],
                "faculty_id": user["faculty_id"],
                "total_hours": data["total_hours"]
            })

    return jsonify(result)



@app.route('/get_faculty_overtime_details', methods=['GET'])
def get_faculty_overtime_details():
    email = request.args.get('email', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    if not email or not start_date or not end_date:
        return jsonify({"error": "Missing required parameters"}), 400

    # Query to get all overtime records for a specific faculty
    overtime_records = overtime_collection.find({
        "email": email,
        "date": {"$gte": start_date, "$lte": end_date}
    })

    result = []
    for record in overtime_records:
        result.append({
            "date": record["date"],
            "start_time": record["start_time"],
            "end_time": record["end_time"],
            "hours_worked": record["hours_worked"],
            "description": record["description"]
        })

    return jsonify(result)

@app.route('/fetch_timetables', methods=['GET'])
def fetch_timetables():
    timetables = list(timetable_collection.find({}, {"_id": 1, "semester": 1}))
    for tt in timetables:
        tt['_id'] = str(tt['_id'])  # Convert ObjectId to string
    return jsonify({"timetables": timetables})


@app.route('/view_timetable/<id>')
def view_timetable(id):
    # Find the timetable by its ID
    timetable = timetable_collection.find_one({'_id': ObjectId(id)})

    if timetable:
        timetable['_id'] = str(timetable['_id'])  # Convert ObjectId to string
        return render_template('view_timetable.html', timetable=timetable)
    else:
        return 'Timetable not found', 404

@app.route('/delete_timetable/<string:timetable_id>', methods=['DELETE'])
def delete_timetable(timetable_id):
    result = timetable_collection.delete_one({"_id": ObjectId(timetable_id)})
    if result.deleted_count == 0:
        return jsonify({"error": "Timetable not found"}), 404
    return jsonify({"message": "Timetable deleted successfully"}), 200


def assign_time_slots(course_type, theory_hours_per_week, semester, teacher_id, existing_semester_slots=None):
    """
    Assigns time slots for a course ensuring no overlap and varied timings across days.
    """
    if existing_semester_slots is None:
        existing_semester_slots = set()

    # Get all existing schedules for this teacher across all semesters
    teacher_schedules = db.timetable.find({"courses.teacher_id": teacher_id})

    # Define time blocks
    morning_slots = ["09:00-10:00", "10:00-11:00"]
    mid_slots = ["11:30-12:30", "12:30-1:30"]
    afternoon_slots = ["2:30-3:30", "3:30-4:30"]

    # Define days
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    # Create 1-hour slots with varied timings
    one_hour_slots = []
    for day in days:
        for slot in morning_slots + mid_slots + afternoon_slots:
            one_hour_slots.append(f"{day} {slot}")

    # Create 2-hour slots with varied timings
    two_hour_slots = []
    for day in days:
        two_hour_slots.extend([
            f"{day} 09:00-11:00",
            f"{day} 11:30-1:30",
            f"{day} 2:30-4:30"
        ])

    def slots_overlap(slot1, slot2):
        day1 = slot1.split(' ')[0]
        day2 = slot2.split(' ')[0]

        if day1 != day2:
            return False

        time1 = slot1.split(' ')[1]
        time2 = slot2.split(' ')[1]

        start1, end1 = time1.split('-')
        start2, end2 = time2.split('-')

        def convert_time(t):
            if t == '1:30':
                return 13.5
            if t == '2:30':
                return 14.5
            if t == '3:30':
                return 15.5
            if t == '4:30':
                return 16.5
            if ':' not in t:
                return float(t.split(':')[0])
            hour, minute = map(int, t.split(':'))
            return hour + (minute / 60)

        start1 = convert_time(start1)
        end1 = convert_time(end1)
        start2 = convert_time(start2)
        end2 = convert_time(end2)

        return not (end1 <= start2 or start1 >= end2)

    # Get teacher's occupied slots
    teacher_occupied_slots = set()
    for schedule in teacher_schedules:
        for course in schedule['courses']:
            if course['teacher_id'] == teacher_id:
                teacher_occupied_slots.update(course['slots'])

    # Remove slots that overlap with existing semester slots or teacher slots
    available_1h = set(one_hour_slots)
    available_2h = set(two_hour_slots)

    # Remove slots that overlap with existing slots
    available_1h = {slot for slot in available_1h
                    if not any(slots_overlap(slot, existing)
                               for existing in existing_semester_slots | teacher_occupied_slots)}

    available_2h = {slot for slot in available_2h
                    if not any(slots_overlap(slot, existing)
                               for existing in existing_semester_slots | teacher_occupied_slots)}

    # Helper function to get time block (morning, mid, afternoon)
    def get_time_block(slot):
        time = slot.split(' ')[1]
        start = time.split('-')[0]
        if start in ["09:00", "10:00"]:
            return "morning"
        elif start in ["11:30", "12:30"]:
            return "mid"
        else:
            return "afternoon"

    assigned_slots = []
    assigned_days = set()
    used_time_blocks = set()  # Track which time blocks we've used

    if course_type == "theory+practical":
        # First assign theory hours with varied timings
        available_1h = sorted(list(available_1h))
        for block in ["morning", "mid", "afternoon"]:
            if len(assigned_slots) >= theory_hours_per_week:
                break
            # Filter slots by current time block
            block_slots = [slot for slot in available_1h
                           if get_time_block(slot) == block and
                           slot.split(' ')[0] not in assigned_days]

            if block_slots:
                slot = block_slots[0]
                assigned_slots.append(slot)
                assigned_days.add(slot.split(' ')[0])
                used_time_blocks.add(get_time_block(slot))

        if len(assigned_slots) < theory_hours_per_week:
            # If we still need more slots, fill from remaining available slots
            remaining_slots = [slot for slot in available_1h
                               if slot.split(' ')[0] not in assigned_days]

            for slot in remaining_slots:
                if len(assigned_slots) >= theory_hours_per_week:
                    break
                assigned_slots.append(slot)
                assigned_days.add(slot.split(' ')[0])

        # Then assign practical slot
        available_2h = sorted(list(available_2h))
        practical_assigned = False
        for slot in available_2h:
            day = slot.split(' ')[0]
            if day not in assigned_days:
                assigned_slots.append(slot)
                practical_assigned = True
                break

        if not practical_assigned:
            raise ValueError(f"Unable to assign practical slot for teacher {teacher_id}")

    else:  # Theory only
        # Assign theory hours with varied timings
        available_1h = sorted(list(available_1h))
        for block in ["morning", "mid", "afternoon"]:
            if len(assigned_slots) >= theory_hours_per_week:
                break
            # Filter slots by current time block
            block_slots = [slot for slot in available_1h
                           if get_time_block(slot) == block and
                           slot.split(' ')[0] not in assigned_days]

            if block_slots:
                slot = block_slots[0]
                assigned_slots.append(slot)
                assigned_days.add(slot.split(' ')[0])
                used_time_blocks.add(get_time_block(slot))

        if len(assigned_slots) < theory_hours_per_week:
            # If we still need more slots, fill from remaining available slots
            remaining_slots = [slot for slot in available_1h
                               if slot.split(' ')[0] not in assigned_days]

            for slot in remaining_slots:
                if len(assigned_slots) >= theory_hours_per_week:
                    break
                assigned_slots.append(slot)
                assigned_days.add(slot.split(' ')[0])

    if len(assigned_slots) < (theory_hours_per_week + (1 if course_type == "theory+practical" else 0)):
        raise ValueError(f"Unable to assign all required slots for teacher {teacher_id}")

    return assigned_slots


@app.route("/generate_timetable", methods=['GET', 'POST'])
def generate_timetable():
    if request.method == 'GET':
        return render_template("timetable.html")
    if request.method == 'POST':
        try:
            semester_type = request.form['sem-type']
            semester = request.form['semester']
            num_courses = int(request.form['num-courses'])

            # Track all assigned slots for this semester
            semester_slots = set()
            courses = []

            # Process each course
            for i in range(num_courses):
                course_name = request.form[f'course_{i}']
                faculty_name = request.form[f'faculty_{i}']
                teacher_id = request.form[f'teacher_id_{i}']
                theory_hours = int(request.form[f'hours_per_week_{i}'])
                course_type = request.form[f'course_type_{i}']

                try:
                    # Pass the current semester slots to check for conflicts
                    assigned_slots = assign_time_slots(
                        course_type,
                        theory_hours,
                        semester,
                        teacher_id,
                        semester_slots
                    )

                    # Update semester slots with newly assigned slots
                    semester_slots.update(assigned_slots)

                    total_hours = theory_hours + (2 if course_type == "theory+practical" else 0)

                    course_entry = {
                        'course_name': course_name,
                        'faculty_name': faculty_name,
                        'teacher_id': teacher_id,
                        'course_type': course_type,
                        'theory_hours': theory_hours,
                        'total_hours': total_hours,
                        'slots': assigned_slots
                    }

                    courses.append(course_entry)

                except ValueError as e:
                    flash(f"Error scheduling {course_name}: {str(e)}")
                    return redirect(url_for('generate_timetable'))

            # Save the semester timetable
            db.timetable.insert_one({
                "semester": semester,
                "courses": courses
            })
            print("Done")
            return redirect(url_for('admin-dashboard'))

        except Exception as e:
            flash(f"Error generating timetable: {str(e)}")
            return redirect(url_for('generate_timetable'))





@app.route('/teacher-login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Find the user in the database
        user = db.users.find_one({"email": email})

        # Verify the password correctly
        if user and check_password_hash(user['password'], password):
            session["email"] = email  # Store email in session
            flash('Login successful', 'success')
            return redirect(url_for('teacher_entry'))  # Redirect to teacher-entry.html
        else:
            flash('Invalid email or password', 'error')
            return redirect(url_for('teacher_login'))

    return render_template('teacher-login.html')


@app.route('/teacher-signup', methods=['GET', 'POST'])
def teacher_signup():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        faculty_id = request.form['faculty_id'].strip()
        name = request.form['name'].strip()
        department = request.form['department'].strip()
        roles = request.form['roles'].strip()

        try:
            existing_user = db.users.find_one({"email": email})
            if existing_user:
                flash('A user with this email already exists. Please log in.', 'error')
                return redirect(url_for('teacher_login'))

            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

            user_data = {
                'email': email,
                'password': hashed_password,
                'faculty_id': faculty_id,
                'name': name,
                'department': department,
                'roles': roles
            }

            db.users.insert_one(user_data)
            flash('Signup successful! Please login.', 'success')
            return redirect(url_for('teacher_login'))

        except Exception as e:
            print(f"Error during signup: {str(e)}")
            flash(f"An error occurred while creating your account: {str(e)}", 'error')
            return redirect(url_for('teacher_signup'))

    return render_template('teacher-signup.html')


@app.route('/teacher-entry')
def teacher_entry():
    if "email" not in session:
        flash("Please log in first", "error")
        return redirect(url_for("teacher_login"))
    return render_template('teacher-entry.html')


@app.route('/teacher-view-timetable')
def teacher_view_timetable():
    if "email" not in session:
        flash("Please log in first", "error")
        return redirect(url_for("teacher_login"))

    email = session["email"]

    # Fetching user details (faculty_id) from users collection
    user = users_collection.find_one({"email": email})
    if not user:
        flash("User not found!", "error")
        return redirect(url_for("teacher_login"))

    faculty_id = user.get("faculty_id")

    # Fetching timetable entries for the specific faculty_id
    timetable_entries = timetable_collection.find({"courses.teacher_id": faculty_id})

    if not timetable_entries:
        flash("No timetable found for this teacher.", "info")
        return redirect(url_for("teacher_dashboard"))

    # List to store timetable information
    slots = []

    # Looping through each timetable entry
    for entry in timetable_entries:
        semester = entry.get("semester")

        # Looping through each course and checking for the teacher_id
        for course in entry.get("courses", []):
            if course.get("teacher_id") == faculty_id:
                course_name = course.get("course_name")
                slots_list = course.get("slots", [])

                # Ensure each slot has the correct day and time, and add it to the slots list
                for slot in slots_list:
                    day_time = slot.split(" ", 1)  # Split the day and time (e.g., "Monday 9:00-10:00")

                    if len(day_time) == 2:
                        day, time = day_time

                        # Split the time range if it is a 2-hour slot
                        time_range = time.split("-")
                        if len(time_range) == 2:
                            start_time, end_time = time_range

                            # Check if the slot duration is more than 1 hour (i.e., 2-hour slot)
                            start_hour, start_minute = map(int, start_time.split(":"))
                            end_hour, end_minute = map(int, end_time.split(":"))

                            if end_hour - start_hour >= 1:  # If the slot is more than 1 hour, split it
                                # Split into two one-hour slots
                                first_slot = f"{start_hour}:{start_minute:02d}-{start_hour + 1}:{start_minute:02d}"
                                second_slot = f"{start_hour + 1}:{start_minute:02d}-{end_hour}:{end_minute:02d}"

                                # Add the two new slots
                                slots.append({
                                    "course_name": course_name,
                                    "slot": first_slot,
                                    "semester": semester,
                                    "day": day
                                })
                                slots.append({
                                    "course_name": course_name,
                                    "slot": second_slot,
                                    "semester": semester,
                                    "day": day
                                })
                            else:
                                # If the slot is exactly 1 hour, just add it normally
                                slots.append({
                                    "course_name": course_name,
                                    "slot": time,
                                    "semester": semester,
                                    "day": day
                                })

    # Pass the slots to the template
    return render_template('teacher-view-timetable.html', slots=slots)
@app.route('/update-overtime')
def update_overtime():
    if "email" not in session:
        flash("Please log in first", "error")
        return redirect(url_for("teacher_login"))
    return render_template('teacher-dashboard.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('entry'))

if __name__ == "__main__":
    app.run(debug=True)
