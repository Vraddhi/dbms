from pymongo import MongoClient
from flask import Flask, render_template, url_for, request, redirect, flash

app = Flask(__name__)
client = MongoClient("mongodb://localhost:27017/")
db = client["management_dbms"]


@app.route("/")
def entry():
    return render_template('mainentry.html')

@app.route('/login', methods=['GET', 'POST'])
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
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('signup'))

        existing_user = db.users.find_one({"email": email})
        if existing_user:
            flash('Email already registered!', 'error')
            return redirect(url_for('signup'))

        db.users.insert_one({"email": email, "password": password})

        flash('Signup successful!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('signup.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        admin = db.admins.find_one({"email": email})

        if admin and password == admin['password']:
            print("Success")# Password verification without hashing
            return redirect(url_for('admin_dashboard'))
        else:
            print("Error")
            flash('Invalid admin email or password', 'error')
            return redirect(url_for('admin_login'))
    return render_template('admin-login.html')

@app.route('/dashboard')
def dashboard():
    return 'User Dashboard'

@app.route('/admin-dashboard')
def admin_dashboard():
    return render_template('admin-entry.html')


@app.route('/add_course', methods=['GET', 'POST'])
def add_course():
    if request.method == 'POST':
        # Extract form data
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

        db.courses.insert_one({"semester": semester,"course_id": course_id,"course_name": course_name,"course_type": course_type})
        flash(f"Course '{course_name}' added successfully!", "success")
        return redirect('/admin-dashboard')
    return render_template('courses.html')


@app.route("/addtimetable", methods=['GET', 'POST'])
def add_timetable():
    if request.method == 'POST':
        sem = request.form.get('sem')
        year = request.form.get('year')
        scheme = request.form.get('scheme')
        dept = request.form.get('dept')

        days = request.form.getlist('day[]')
        slot_lists = request.form.getlist('slot[]')
        course_lists = request.form.getlist('course[]')
        teacher_lists = request.form.getlist('teacher[]')

        timetable_entry = {
            'semester': sem,
            'year': year,
            'scheme': scheme,
            'department': dept,
            'entries': []
        }

        for day, slots, courses, teachers in zip(days, slot_lists, course_lists, teacher_lists):
            entries = []
            for slot, course, teacher in zip(slots.split(','), courses.split(','), teachers.split(',')):
                entries.append({
                    'day': day,
                    'slot': slot.strip(),
                    'course': course.strip(),
                    'teacher': teacher.strip()
                })
            timetable_entry['entries'].extend(entries)
        db.timetable.insert_one(timetable_entry)
        return redirect(url_for('success'))
    return render_template('timetable.html')


@app.route('/success')
def success():
    return "Timetable successfully added!"

if __name__ == "__main__":
    app.run(debug=True)
