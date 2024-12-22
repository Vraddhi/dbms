from flask import Flask, render_template, request, redirect, url_for, flash
from pymongo import MongoClient
import random

app = Flask(__name__)
app.secret_key = 'your_secret_key'

client = MongoClient("mongodb://localhost:27017/")
db = client["DBMS_LAB"]

time_slots = [
    "Monday 09:00-10:00", "Monday 10:00-11:00", "Monday 11:30-12:30", "Monday 12:30-1:30", "Monday 2:30-3:30", "Monday 3:30-4:30",
    "Tuesday 09:00-10:00", "Tuesday 10:00-11:00", "Tuesday 11:30-12:30", "Tuesday 12:30-1:30", "Tuesday 2:30-3:30", "Tuesday 3:30-4:30",
    "Wednesday 09:00-10:00", "Wednesday 10:00-11:00", "Wednesday 11:30-12:30", "Wednesday 12:30-1:30", "Wednesday 2:30-3:30", "Wednesday 3:30-4:30",
    "Thursday 09:00-10:00", "Thursday 10:00-11:00", "Thursday 11:30-12:30", "Thursday 12:30-1:30", "Thursday 2:30-3:30", "Thursday 3:30-4:30",
    "Friday 09:00-10:00", "Friday 10:00-11:00", "Friday 11:30-12:30", "Friday 12:30-1:30", "Friday 2:30-3:30", "Friday 3:30-4:30"
]

def assign_time_slots(courses):
    timetable = []
    available_slots = time_slots[:]

    for course in courses:
        course_hours = int(course['hours_per_week'])
        assigned_slots = []

        for _ in range(course_hours):
            if available_slots:
                selected_slot = random.choice(available_slots)
                available_slots.remove(selected_slot)
                assigned_slots.append(selected_slot)
            else:
                flash('Not enough time slots available to assign all courses.', 'error')
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

@app.route('/check_teacher_ot')
def check_teacher_ot():
    teacher_ots = db.teachers.find()
    return render_template('admin-view-OT.html', teachers=teacher_ots)

@app.route("/generate_timetable", methods=['GET', 'POST'])
def generate_timetable():
    if request.method == 'POST':
        semester_type = request.form.get('sem-type')
        semester = request.form.get('semester')
        college_start_time = request.form.get('college-start-time')
        college_end_time = request.form.get('college-end-time')
        num_courses = int(request.form.get('num-courses', 0))

        courses = []
        for i in range(num_courses):
            course_name = request.form.get(f'course_{i}')
            faculty_name = request.form.get(f'faculty_{i}')
            teacher_id = request.form.get(f'teacher_id_{i}')
            hours_per_week = request.form.get(f'hours_per_week_{i}')
            
            if course_name and faculty_name and teacher_id and hours_per_week:
                courses.append({
                    'course_name': course_name,
                    'faculty_name': faculty_name,
                    'teacher_id': teacher_id,
                    'hours_per_week': hours_per_week
                })

        timetable = assign_time_slots(courses)
        
        if timetable is None:
            return redirect(url_for('generate_timetable'))

        timetable_entry = {
            'semester_type': semester_type,
            'semester': semester,
            'college_start_time': college_start_time,
            'college_end_time': college_end_time,
            'courses': timetable
        }

        db.timetable.insert_one(timetable_entry)
        flash('Timetable generated successfully!', 'success')
        return redirect(url_for('dummy'))

    return render_template('timetable.html')

@app.route('/dummy')
def dummy():
    return render_template('dummy.html')

@app.route("/ocr_timetable", methods=['GET', 'POST'])
def ocr_timetable():
    if request.method == 'POST':
        flash('OCR Timetable generated successfully!', 'success')
        return redirect(url_for('success'))

    return render_template('OCR.html')

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
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = db.users.find_one({"email": email})

        if user and password == user['password']:
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')
            return redirect(url_for('login'))
    return render_template('teacher-login.html')

@app.route('/dashboard')
def dashboard():
    return 'User Dashboard'

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

if __name__ == "__main__":
    app.run(debug=True)
