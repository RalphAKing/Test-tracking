from flask import Flask, render_template, request, redirect, session, jsonify, url_for, Response
import uuid
from yaml.loader import SafeLoader
import yaml
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, FrameBreak
from reportlab.lib.styles import getSampleStyleSheet
import io
import csv

#--Done--
# This code snippet initializes the Flask application and configures its settings.
# It performs the following steps:
# 1. Creates an instance of the Flask class with the specified static folder.
# 2. Sets the secret key for the Flask application to enable session management and other secure features.
# 3. Updates the Jinja environment globals to include the zip function, allowing it to be used within Jinja templates.
app = Flask(__name__, static_folder='static')
app.secret_key = 'secret_key'
app.jinja_env.globals.update(zip=zip)

#--Done--
# This code snippet loads configuration settings from a YAML file.
# It performs the following steps:
# 1. Opens the 'config.yaml' file.
# 2. Loads the content of the file using the SafeLoader of the yaml module.
# 3. Stores the loaded configuration settings in the variable 'config'.
with open('config.yaml') as f:
    config = yaml.load(f, Loader=SafeLoader)

#--Done--
# This function connects to the MongoDB database and returns the test data collection.
# It performs the following steps:
# 1. Creates a MongoClient object using the MongoDB address from the config.
# 2. Connects to the "TestTracking" database.
# 3. Retrieves the "data" collection from the database.
# 4. Returns the test data collection.
def testdb():
    cluster = MongoClient(config['mongodbaddress'], connect=False)
    db = cluster["TestTracking"]
    testdbs = db["data"]
    return testdbs

#--Done--
# This function connects to the MongoDB database and returns the accounts collection.
# It performs the following steps:
# 1. Creates a MongoClient object using the MongoDB address from the config.
# 2. Connects to the "TestTracking" database.
# 3. Retrieves the "accounts" collection from the database.
# 4. Returns the accounts collection.
def accounts():
    cluster = MongoClient(config['mongodbaddress'], connect=False)
    db = cluster["TestTracking"]
    accountsdb = db["accounts"]
    return accountsdb

#--Done--
# This function checks if a user is logged in.
# It performs the following steps:
# 1. Checks if 'user' and 'user_id' are in the session.
# 2. Connects to the database to retrieve the user information based on the session data.
# 3. If the user is found, updates the session with the user's type.
# 4. Returns True if the user is found in the database.
# 5. Returns False if the user is not found in the session or database.
def is_logged_in():
    if 'user' in session and 'user_id' in session:
        db = accounts()
        user = db.find_one({'username': session['user'], 'user_id': session['user_id']})
        if user: 
            session['user_type'] = user['type'] 
        return True
    return False

#--Done--
# This function calculates grade boundaries and generates a graph of student scores.
# It performs the following steps:
# 1. Defines the percentiles and grades for the grade boundaries.
# 2. Calculates the percentile ranks for the given scores.
# 3. Defines an inner function to assign grades based on the calculated percentile ranks.
# 4. Assigns grades to the student scores using the inner function.
# 5. Creates a DataFrame with the scores and assigned grades.
# 6. Plots a histogram of the scores and adds vertical lines and labels for the grade boundaries.
# 7. Constructs the filename for the graph image and creates directories if they do not exist.
# 8. Saves the histogram plot as a PNG image with a transparent background.
# 9. Connects to the database to update the grade boundaries for the given subject, year, and test name.
# 10. Iterates through the student averages and updates their subject information with the average score and assigned grade.
def calculate_boundaries_and_graph(scores, subject, year, student_averages, school_name, test_name=None):
    percentiles = [90, 80, 70, 60, 50, 40, 0]
    grades = ['A*', 'A', 'B', 'C', 'D', 'E', 'U']
    percentile_ranks = np.percentile(scores, percentiles)
    def assign_grade(score):
        for i, perc in enumerate(percentile_ranks):
            if score >= perc:
                return grades[i]
    student_grades = [assign_grade(score) for score in scores]
    df = pd.DataFrame({'Score': scores, 'Grade': student_grades})
    plt.figure(figsize=(12, 8))
    sns.histplot(scores, bins=20, kde=True, edgecolor='k', alpha=0.7)
    for i, perc in enumerate(percentile_ranks):
        plt.axvline(perc, color='r', linestyle='--', linewidth=1)
        plt.text(perc, plt.ylim()[1] * 0.9, f'{grades[i]} ({int(perc)})', color='r', ha='center', va='bottom')
    plt.xlabel('Scores')
    plt.ylabel('Number of Students')
    subject_year = f"{subject}-Y{year}"
    filename = f'static/subject_years/{school_name}/{subject_year}/{test_name if test_name else subject_year}.png'
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    plt.savefig(filename, transparent=True)
    db = testdb()
    grade_boundaries = {grade: rank for grade, rank in zip(grades, percentile_ranks)}
    db.update_one(
        {'subject': subject, 'year': year, 'tests.test_name': test_name},
        {'$set': {'tests.$.grade_boundaries': grade_boundaries}}
    )
    for student_id, average_score in student_averages.items():
        grade = assign_grade(average_score)
        update_student_subjects(student_id, subject_year, average_score, grade, test_name)

#--Done--
# This function updates the subject information for a specific student.
# It performs the following steps:
# 1. Connects to the database to retrieve student information.
# 2. Finds the student document based on the student_id.
# 3. If the student document is not found, exits the function.
# 4. Checks if the student document has a 'subjects' field that is a list:
#    - If not, initializes the 'subjects' field as an empty list in the database.
# 5. Checks if there is an existing subject entry for the given subject year and test name:
#    - If an existing subject is found, updates the average percentage and grade in the database.
#    - If no existing subject is found, adds a new subject entry with the subject year, test name, average percentage, and grade to the database.
def update_student_subjects(student_id, subject_year, average_score, grade, test_name=None):
    db = testdb()
    student_doc = db.find_one({'user_id': student_id})
    if not student_doc:
        return
    if 'subjects' not in student_doc or not isinstance(student_doc['subjects'], list):
        db.update_one(
            {'user_id': student_id},
            {'$set': {'subjects': []}}
        )
    existing_subject = next((subj for subj in student_doc['subjects'] if subj['subject_year'] == subject_year and subj['test_name'] == test_name), None)
    if existing_subject:
        db.update_one(
            {'user_id': student_id, 'subjects.subject_year': subject_year, 'subjects.test_name': test_name},
            {'$set': {
                'subjects.$.average_percentage': average_score,
                'subjects.$.grade': grade
            }}
        )
    else:
        db.update_one(
            {'user_id': student_id},
            {'$push': {
                'subjects': {
                    'subject_year': subject_year,
                    'test_name': test_name,
                    'average_percentage': average_score,
                    'grade': grade
                }
            }}
        )

#--Done--
# This function performs a mass update of grades for a given school.
# It performs the following steps:
# 1. Connects to the databases to retrieve class and student information.
# 2. Finds all classes for the given school.
# 3. Initializes a dictionary to store scores for each subject and year combination.
# 4. Iterates through each class and test to collect student marks and calculate percentages:
#    - Retrieves the subject and year for each test.
#    - Stores student IDs and percentages in the subject_year_scores dictionary.
# 5. Iterates through each subject year and scores to calculate average scores and update grades:
#    - Calculates the average percentage for each student.
#    - Prepares a dictionary of student average scores.
#    - Splits the subject year string to get the subject and year.
#    - Calls the calculate_boundaries_and_graph function to update grade boundaries and generate graphs.
def mass_update_grades_for_school(school_name):
    db = testdb()
    classes = db.find({'school': school_name})
    subject_year_scores = {}
    for class_entry in classes:
        year = class_entry.get('year')
        for test in class_entry.get('tests', []):
            subject = test['subject']
            subject_year = f"{subject}-Y{year}"
            if subject_year not in subject_year_scores:
                subject_year_scores[subject_year] = []
            for student_id, marks in test['students_marks'].items():
                percentage = marks['percentage']
                subject_year_scores[subject_year].append((student_id, percentage))
    for subject_year, scores in subject_year_scores.items():
        if scores:
            percentages = [score[1] for score in scores]
            student_averages = {}
            for student_id, percentage in scores:
                if student_id not in student_averages:
                    student_averages[student_id] = []
                student_averages[student_id].append(percentage)
            average_scores = {student_id: round((sum(percentages) / len(percentages)),1) for student_id, percentages in student_averages.items()}
            subject, year = subject_year.split('-Y')
            calculate_boundaries_and_graph(percentages, subject, year, average_scores, school_name)

#--Done--
# This function handles the main index page and redirects users based on their user type.
# It performs the following steps:
# 1. Defines the route for the index function.
# 2. Checks if the user is logged in and retrieves their user type from the session.
# 3. If the user type is 'admin':
#    - Connects to the database to retrieve subject and year data.
#    - Constructs a set and dictionary of subject years with available images.
#    - Retrieves a list of students and classes.
#    - Attempts to retrieve and remove 'existing_users' and 'caerror' from the session.
#    - Renders the 'admin.html' template with the gathered data.
# 4. If the user type is 'teacher':
#    - Connects to the database to retrieve a list of classes taught by the teacher.
#    - Counts the number of students in each class.
#    - Renders the 'teacher.html' template with the list of classes.
# 5. If the user type is 'student':
#    - Connects to the database to retrieve the list of classes the student is enrolled in.
#    - Constructs a dictionary to store the student's average percentage and grade for each subject year.
#    - Calculates the average percentage for each subject year.
#    - Defines an inner function to assign grades based on percentage and grade boundaries.
#    - Retrieves and assigns grades for each subject year.
#    - Renders the 'student.html' template with the list of classes and subjects years data.
# 6. If the user is not logged in, renders the 'index.html' template.
@app.route('/')
def index():
    user_type = ''
    if is_logged_in():
        user_type = session.get('user_type')
        if user_type == 'admin':
            db = testdb()
            subjects_years_cursor = db.find({}, {'subject': 1, 'year': 1})
            subjects_year_data = {}
            subject_years = set()
            for entry in subjects_years_cursor:
                subject = entry.get('subject')
                year = entry.get('year')
                if subject and year:
                    subject_year = f"{subject}-Y{year}"
                    school_name=session['school']
                    image_path = f'static/subject_years/{school_name}/{subject_year}/{subject_year}.png'
                    if os.path.exists(image_path):
                        subject_years.add(subject_year)
                        if subject not in subjects_year_data:
                            subjects_year_data[subject] = []
                        if year not in subjects_year_data[subject]:
                            subjects_year_data[subject].append(year)
            students = list(accounts().find({'type': 'student'}, {'username': 1, 'user_id': 1}))
            classes = list(testdb().find({'classname': {'$ne': '', '$exists': True}}, {'classname': 1, 'year': 1, 'code': 1}))
            try:
                existing_users = session.get('existing_users', [])
                session.pop('existing_users')
            except:
                existing_users=[]
            try:
                caerror=session.get('caerror', '')
                session.pop('caerror')
            except:
                caerror=None
            return render_template('admin.html', subjects_year_data=subjects_year_data, subject_years=subject_years, students=students, classes=classes, existing_users=existing_users,caerror=caerror, school_name=session['school'])
        elif user_type == 'teacher':
            db = testdb()
            classes = list(db.find({
                '$or': [
                    {'teacher': session['user_id']},
                    {'teachers': session['user_id']}
                ]
            }))
            for class_entry in classes:
                class_entry['num_students'] = len(class_entry.get('students', []))
            return render_template('teacher.html', classes=classes)
        elif user_type == 'student':
            db = testdb()
            student_id = session['user_id']
            classes = list(db.find({'students': student_id}))
            subjects_years = {}
            for class_entry in classes:
                year = class_entry.get('year', 'N/A')
                for test in class_entry.get('tests', []):
                    if student_id in test['students_marks']:
                        percentage = test['students_marks'][student_id]['percentage']
                        subject = test['subject']
                        subject_year = f"{subject}-Y{year}"
                        if subject_year not in subjects_years:
                            subjects_years[subject_year] = {'total_percentage': 0, 'count': 0}
                        subjects_years[subject_year]['total_percentage'] += percentage
                        subjects_years[subject_year]['count'] += 1
            for subject_year in subjects_years:
                subjects_years[subject_year]['average_percentage'] = round((subjects_years[subject_year]['total_percentage'] / subjects_years[subject_year]['count']), 1)
            def assign_grade(percentage, grade_boundaries):
                for grade_letter, boundary in sorted(grade_boundaries.items(), key=lambda x: x[1], reverse=True):
                    if percentage >= boundary:
                        return grade_letter
                return 'U'
            for subject_year in subjects_years:
                subject, year = subject_year.split('-Y')
                grade_boundaries = db.find_one({'subject_year': subject_year, 'test_name': None}, {'grade_boundaries': 1, '_id': 0})
                if grade_boundaries:
                    grade_boundaries = grade_boundaries.get('grade_boundaries', {})
                    average_percentage = subjects_years[subject_year]['average_percentage']
                    grade = assign_grade(average_percentage, grade_boundaries)
                    subjects_years[subject_year]['grade'] = grade
                else:
                    subjects_years[subject_year]['grade'] = 'N/A'
            return render_template('student.html', classes=classes, subjects_years=subjects_years)
    return render_template('index.html')

#--Done--
# This function handles the view for the login and signup page.
# It performs the following steps:
# 1. Defines the route and method for the login_signup function.
# 2. Checks if the user is logged in.
# 3. If the user is logged in, redirects to the home page.
# 4. Connects to the database to retrieve a distinct list of schools.
# 5. Renders the 'login-signup.html' template with the list of schools.
@app.route('/login-signup')
def login_signup():
    if is_logged_in():
        return redirect('/')
    db = accounts()
    schools = db.distinct('school')
    return render_template('login-signup.html', schools=schools)

#--Done--
# This function handles the signup process for new users.
# It performs the following steps:
# 1. Defines the route and method for the signup function.
# 2. Connects to the database to store user information.
# 3. Retrieves the school, email, username, and password from the submitted form data.
# 4. Hashes the password for security.
# 5. Generates a unique user ID.
# 6. Sets session variables for the user's username, user ID, and school.
# 7. Checks if a user with the same username already exists in the school:
#    - If the username already exists, retrieves the list of schools for the login-signup template.
#    - Renders the 'login-signup.html' template with the list of schools and an error message.
# 8. If the username does not exist, creates a user entry with the provided information.
# 9. Inserts the user entry into the database.
# 10. Redirects to the home page upon successful signup.
@app.route('/signup', methods=['POST'])
def signup():
    db = accounts()
    school = request.form['school']
    email = request.form['email']
    username = (request.form['username']).lower()
    password = generate_password_hash(request.form['password'])
    user_id = str(uuid.uuid4())  
    session['user'] = username
    session['user_id'] = user_id
    session['school'] = school
    existing_user = db.find_one({'school': school, 'username': username})
    if existing_user:
        schools = db.distinct('school')
        return render_template('login-signup.html', schools=schools, error="Username already exists in this school")
    user = {
        'user_id': user_id,
        'school': school,
        'email': email,
        'username': username,
        'password': password,
        'type': "student"
    }
    db.insert_one(user)
    return redirect('/')

#--Done--
# This function handles the login process for users.
# It performs the following steps:
# 1. Defines the route and method for the login function.
# 2. Connects to the database to retrieve user information.
# 3. Retrieves the school, username, and password from the submitted form data.
# 4. Finds the user in the database based on the school and username.
# 5. If the user is found and the password hash matches:
#    - Sets session variables for the user's username, user ID, and school.
#    - Redirects to the home page.
# 6. If the credentials are invalid:
#    - Retrieves the list of schools for the login-signup template.
#    - Renders the 'login-signup.html' template with the list of schools and an error message.
@app.route('/login', methods=['POST'])
def login():
    db = accounts()
    school = request.form['school']
    username = (request.form['username']).lower()
    password = request.form['password']
    user = db.find_one({'school': school, 'username': username})
    if user and check_password_hash(user['password'], password):
        session['user'] = user['username']
        session['user_id'] = user['user_id']  
        session['school'] = user['school']
        return redirect('/')
    schools = db.distinct('school')
    return render_template('login-signup.html', schools=schools, error="Invalid credentials")

# This function handles the creation of a new school.
# It performs the following steps:
# 1. Defines the route and methods (GET and POST) for the create_school function.
# 2. If the request method is POST:
#    - Retrieves the admin password from the submitted form data.
#    - Checks if the admin password matches the configured password; if not, returns a 403 error.
#    - Retrieves the school name, admin email, admin username, and admin account password from the form data.
#    - Hashes the admin account password for security.
#    - Connects to the database to store the admin user information.
#    - Creates an admin user entry with a unique user ID, school name, email, username, hashed password, and user type 'admin'.
#    - Inserts the admin user entry into the database.
#    - Redirects to the login/signup page upon successful school creation.
# 3. If the request method is GET, renders the 'createschool.html' template for the school creation form.
@app.route('/create_school', methods=['GET', 'POST'])
def create_school():
    if request.method == 'POST':
        admin_password = request.form['admin_password']
        if admin_password != config['adminpassword']:
            return "Invalid admin password", 403
        school_name = request.form['school_name']
        admin_email = request.form['admin_email']
        admin_username = request.form['admin_username']
        admin_account_password = generate_password_hash(request.form['admin_account_password'])
        db = accounts()
        admin_user = {
            'user_id': str(uuid.uuid4()), 
            'school': school_name,
            'email': admin_email,
            'username': admin_username,
            'password': admin_account_password,
            'type': 'admin'
        }
        db.insert_one(admin_user)
        return redirect(url_for('login_signup'))
    return render_template('createschool.html')

#--Done--
# This function handles the creation of a new user account by an admin.
# It performs the following steps:
# 1. Defines the route and method for the create_account function.
# 2. Checks if the user is logged in and if their user type is 'admin'.
# 3. Retrieves the user type, username, email, and password from the submitted form data.
# 4. Hashes the password for security.
# 5. Retrieves the school from the session and generates a unique user ID.
# 6. Connects to the database to check if the username already exists in the school.
# 7. If the username already exists, returns a 400 error with an appropriate message.
# 8. If the username does not exist, creates a user entry with the provided information.
# 9. Inserts the user entry into the database.
# 10. Redirects to the home page upon successful account creation.
# 11. Redirects to the home page if the user is not logged in or does not have the correct user type.
@app.route('/create_account', methods=['POST'])
def create_account():
    if is_logged_in() and session.get('user_type') == 'admin':
        user_type = request.form['user_type']
        username = (request.form['username']).lower()
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        school = session['school']
        user_id = str(uuid.uuid4())
        db = accounts()
        existing_user = db.find_one({'username': username, 'school': school})
        if existing_user:
            session['caerror'] = "Username already exists in this school"
            return redirect('/')
        user = {
            'user_id': user_id,
            'username': username,
            'email': email,
            'password': password,
            'school': school,
            'type': user_type
        }
        db.insert_one(user)
        return redirect('/')
    return redirect('/')

#--
# This function handles the update of school grades by an admin.
# It performs the following steps:
# 1. Defines the route and method for the update_school function.
# 2. Checks if the user is logged in and if their user type is 'admin'.
# 3. Retrieves the school name from the session.
# 4. Calls the mass_update_grades_for_school function to update the grades for the school.
# 5. Redirects to the home page upon successful grade update.
# 6. Redirects to the home page if the user is not logged in or does not have the correct user type.
@app.route('/update_school', methods=['POST'])
def update_school():
    if is_logged_in() and session.get('user_type') == 'admin':
        school = session['school']
        mass_update_grades_for_school(school)
        return redirect('/')
    return redirect('/')

#--Done--
# This function handles the view for detailed subject information for admins.
# It performs the following steps:
# 1. Defines the route for the subject_details function.
# 2. Checks if the user is logged in and if their user type is 'admin'.
# 3. Connects to the database to retrieve class information for the given subject.
# 4. Initializes dictionaries to store student information and test data.
# 5. Defines an inner function to assign grades based on percentage and grade boundaries.
# 6. Iterates through each class and test to collect student marks and calculate percentages and grades:
#    - Retrieves the student's mark and percentage for each test.
#    - Initializes the grade and stores student information in the students dictionary.
# 7. Calculates the average percentage and grade for each student.
# 8. Prepares the response data with students and tests information.
# 9. Returns the response data as JSON.
# 10. Redirects to the home page if the user is not logged in or does not have the correct user type.
@app.route('/subject_details/<subject>')
def subject_details(subject):
    if is_logged_in() and session.get('user_type') == 'admin':
        db = testdb()
        classes = list(db.find({'subject': subject}))
        students = {}
        tests = []
        def assign_grade(percentage, subject):
            db = testdb()
            grade_boundaries = db.find_one({'subject': subject}, {'grade_boundaries': 1, '_id': 0}).get('grade_boundaries', {})
            for grade_letter, boundary in grade_boundaries.items():
                if percentage >= boundary:
                    return grade_letter
            return 'N/A'
        for class_entry in classes:
            for test in class_entry.get('tests', []):
                if test['subject'] == subject:
                    tests.append({'test_name': test['test_name']})
                    for student_id, marks in test['students_marks'].items():
                        if student_id not in students:
                            student_doc = accounts().find_one({'user_id': student_id}, {'username': 1, 'user_id': 1})
                            students[student_id] = {
                                'username': student_doc['username'],
                                'marks': {},
                                'average_percentage': 0,
                                'grade': 'N/A'
                            }
                        students[student_id]['marks'][test['test_name']] = marks['percentage']
        for student_id, student in students.items():
            total_percentage = sum(student['marks'].values())
            test_count = len(student['marks'])
            student['average_percentage'] = total_percentage / test_count if test_count > 0 else 0
            student['grade'] = assign_grade(student['average_percentage'], subject)
        response = {'students': list(students.values()), 'tests': tests}
        return jsonify(response)
    return redirect('/')

#--done--
# This function handles the view for detailed performance information for a specific student for admins.
# It performs the following steps:
# 1. Defines the route for the admin_student_performance function.
# 2. Checks if the user is logged in and if their user type is 'admin'.
# 3. Defines a dictionary for grade conversion from letter grades to numerical values for under Year 11 students.
# 4. Connects to the databases to retrieve student and class information.
# 5. Retrieves the student's basic information using the student_id.
# 6. Retrieves the list of classes the student is enrolled in.
# 7. Initializes lists and variables to store student marks, total percentage, and test count.
# 8. Iterates through each class and test to collect student marks and calculate percentages and grades:
#    - Retrieves the student's mark and percentage for each test.
#    - Initializes the grade and image path.
#    - If the test has a percentage, processes the grade and image path based on the grading type.
#    - Assigns grades based on the grade boundaries if they exist.
#    - Converts grades to numerical values for under Year 11 students.
#    - Updates the student's marks and the total percentage and test count.
# 9. Calculates the student's average percentage across all tests.
# 10. Renders the 'admin_student_performance.html' template with the student data, marks, average percentage, and class entry.
# 11. Redirects to the home page if the user is not logged in or does not have the correct user type.
@app.route('/admin_student_performance/<student_id>')
def admin_student_performance(student_id):
    if is_logged_in() and session.get('user_type') == 'admin':
        GRADE_CONVERSION = {
        "A*": 9,
        "A": 8,
        "B": 7,
        "C": 6,
        "D": 5,
        "E": 4,
        "U": "U"
    }
        db = testdb()
        accounts_db = accounts()
        student = accounts_db.find_one({'user_id': student_id}, {'username': 1, 'email': 1, 'user_id': 1})
        classes = list(db.find({'students': student_id}))
        student_marks = []
        total_percentage = 0
        test_count = 0
        for class_entry in classes:
            class_year = class_entry.get('year', 'N/A')
            for test in class_entry.get('tests', []):
                if student_id in test['students_marks']:
                    mark_entry = test['students_marks'][student_id]
                    percentage = round(mark_entry['percentage'], 2)
                    grade = 'N/A'
                    image_path = None
                    grade_boundaries = {}
                    if test['grading_type'] == 'curve':
                        grade_boundaries = test.get('grade_boundaries', {})
                        school_name=session['school']
                        image_path = f'/static/subject_years/{school_name}/{class_entry["subject"]}-Y{class_entry["year"]}/{test["test_name"]}.png'
                    else:
                        grade_boundaries = test.get('grade_boundaries', {})
                    if grade_boundaries:
                        for grade_letter, boundary in sorted(grade_boundaries.items(), key=lambda x: x[1], reverse=True):
                            if percentage >= boundary:
                                grade = grade_letter
                                break   
                    if int(class_entry['year']) <= 11 and grade in GRADE_CONVERSION:
                            grade = GRADE_CONVERSION[grade]
                    if int(class_entry['year']) <= 11:
                        grade_boundaries = {GRADE_CONVERSION[grade]: boundary for grade, boundary in grade_boundaries.items()}     
                    student_marks.append({
                        'subject': test['subject'],
                        'test_name': test['test_name'],
                        'year': class_year,
                        'test_type': test['grading_type'].title(),
                        'percentage': percentage,
                        'grade': grade,
                        'image_path': image_path,
                        'grade_boundaries': grade_boundaries
                    })
                    total_percentage += percentage
                    test_count += 1
        average_percentage = round(total_percentage / test_count, 2) if test_count > 0 else 0
        return render_template('admin_student_performance.html', student=student, student_marks=student_marks, average_percentage=average_percentage)
    return redirect('/')

#--done--
# This function handles the view for detailed subject and year information for admins.
# It performs the following steps:
# 1. Defines the route for the admin_subject_year_details function.
# 2. Checks if the user is logged in and if their user type is 'admin'.
# 3. Connects to the database to retrieve grade boundaries and class information.
# 4. Converts the year to a string and constructs a subject_year string.
# 5. Retrieves the grade boundaries entry for the subject and year combination.
# 6. Defines an inner function to assign grades based on percentage and grade boundaries.
# 7. If grade boundaries are found:
#    - Retrieves the list of classes for the subject and year.
#    - Initializes dictionaries to store student information and test data.
#    - Iterates through each class and test to collect student marks.
#    - Calculates the average percentage and grade for each student.
#    - Calculates the average percentage and grade for each test.
#    - Prepares the response data with subject, year, students, and tests information.
#    - Renders the 'admin_subject_year_details.html' template with the response data.
# 8. Redirects to the home page if the user is not logged in or does not have the correct user type.
@app.route('/admin_subject_year_details/<subject>/<year>')
def admin_subject_year_details(subject, year):
    if is_logged_in() and session.get('user_type') == 'admin':
        db = testdb()
        year = str(year)
        subject_year = f"{subject}-Y{year}"
        grade_boundaries_entry = db.find_one({'subject_year': subject_year, 'test_name': None})
        def assign_grade(percentage, grade_boundaries):
            for grade_letter, boundary in sorted(grade_boundaries.items(), key=lambda x: x[1], reverse=True):
                if percentage >= boundary:
                    return grade_letter
            return 'U'
        if grade_boundaries_entry:
            grade_boundaries = grade_boundaries_entry['grade_boundaries']
            classes = list(db.find({'subject': subject, 'year': year}))
            students = {}
            tests = []
            for class_entry in classes:
                for test in class_entry.get('tests', []):
                    if test['subject'] == subject:
                        tests.append({
                            'test_name': test['test_name'],
                            'average_percentage': 0,
                            'grade': 'N/A'
                        })
                        for student_id, marks in test.get('students_marks', {}).items():
                            if student_id not in students:
                                student_doc = accounts().find_one({'user_id': student_id}, {'username': 1, 'user_id': 1})
                                if student_doc:
                                    students[student_id] = {
                                        'username': student_doc['username'],
                                        'marks': {},
                                        'average_percentage': 0,
                                        'grade': 'N/A'
                                    }
                            students[student_id]['marks'][test['test_name']] = marks['percentage']
            for student_id, student_data in students.items():
                total_percentage = sum(student_data['marks'].values())
                test_count = len(student_data['marks'])
                student_data['average_percentage'] = round((total_percentage / test_count), 1) if test_count > 0 else 0
                student_data['grade'] = assign_grade(student_data['average_percentage'], grade_boundaries)
            for test in tests:
                test_name = test['test_name']
                test_scores = [student_data['marks'][test_name] for student_data in students.values() if test_name in student_data['marks']]
                if test_scores:
                    test['average_percentage'] = sum(test_scores) / len(test_scores)
                    test['grade'] = assign_grade(test['average_percentage'], grade_boundaries)
            response = {'subject': subject, 'year': year, 'students': list(students.values()), 'tests': tests}
            return render_template('admin_subject_year_details.html', data=response)
    return redirect('/')

# This function handles the creation of a new class.
# It performs the following steps:
# 1. Defines the route and method for the create_class function.
# 2. Checks if the user is logged in and if their user type is 'teacher'.
# 3. Defines an inner function to generate a unique class code for the school:
#    - Connects to the database and generates a random 5-character code.
#    - Ensures the generated code is unique for the school by checking the database.
# 4. Retrieves the classname, year, school, and subject from the submitted form data.
# 5. Generates a unique class code using the inner function.
# 6. Creates a class entry dictionary with the class details and teacher's user ID.
# 7. Inserts the class entry into the database.
# 8. Redirects to the home page upon successful class creation.
# 9. Redirects to the home page if the user is not logged in or does not have the correct user type.
@app.route('/create_class', methods=['POST'])
def create_class():
    if is_logged_in() and session.get('user_type') == 'teacher':
        def generate_unique_code(school):
            db = testdb()
            while True:
                code = ''.join(np.random.choice(list('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'), size=5))
                if not db.find_one({'school': school, 'code': code}):
                    break
            return code
        classname = request.form['classname']
        year = request.form['year']
        school = session['school']
        subject = request.form['subject']
        class_code = generate_unique_code(school)
        class_entry = {
            'classname': classname,
            'year': year,
            'subject': subject,
            'code': class_code,
            'school': school,
            'teacher': session['user_id']
        }
        db = testdb()
        db.insert_one(class_entry)
        return redirect('/')  
    return redirect('/')

# This function handles the process of joining a class.
# It performs the following steps:
# 1. Defines the route and method for the join_class function.
# 2. Retrieves the class code from the submitted form data.
# 3. Checks if the class code is provided; if not, returns a 400 error.
# 4. Connects to the database to retrieve the class entry based on the class code.
# 5. Extracts the user_id and user_type from the session.
# 6. If the class entry is found, processes the join request based on the user type:
#    - If the user is a teacher:
#      - Adds the teacher to the class entry if not already present.
#      - Updates the class entry in the database.
#      - Adds the class to the teacher's entry if not already present.
#      - Updates the teacher's entry in the database.
#      - Redirects to the view_class page with the class code.
#    - If the user is a student:
#      - Adds the student to the class entry if not already present.
#      - Updates the class entry in the database.
#      - Redirects to the class_tests page with the class code.
# 7. Returns an error message if the class is not found.
@app.route('/join_class', methods=['POST'])
def join_class():
    class_code = request.form.get('class_code')
    if not class_code:
        return "Class code is required", 400
    db = testdb()
    class_entry = db.find_one({'code': class_code})
    user_id = session['user_id']
    user_type = session.get('user_type')
    if class_entry:
        if user_type == 'teacher':
            if 'teachers' not in class_entry:
                class_entry['teachers'] = []
            if user_id not in class_entry['teachers']:
                class_entry['teachers'].append(user_id)
                db.update_one({'code': class_code}, {'$set': {'teachers': class_entry['teachers']}})
            accounts_db = accounts()
            teacher_entry = accounts_db.find_one({'user_id': user_id})
            if 'classes' not in teacher_entry:
                teacher_entry['classes'] = []
            if class_code not in teacher_entry['classes']:
                teacher_entry['classes'].append(class_code)
                accounts_db.update_one({'user_id': user_id}, {'$set': {'classes': teacher_entry['classes']}})
            return redirect(url_for('view_class', class_code=class_code))
        elif user_type == 'student':
            if 'students' not in class_entry:
                class_entry['students'] = []
            if user_id not in class_entry['students']:
                class_entry['students'].append(user_id)
                db.update_one({'code': class_code}, {'$set': {'students': class_entry['students']}})
            return redirect(url_for('class_tests', class_code=class_code))
    return "Class not found", 404

# This function handles the view for a specific class.
# It performs the following steps:
# 1. Defines the route and method for the view_class function.
# 2. Checks if the user is logged in and if their user type is 'teacher'.
# 3. Connects to the databases to retrieve class and student information.
# 4. Retrieves the class entry based on the class code.
# 5. If the class entry is found, retrieves the list of students in the class.
# 6. Iterates through the list of students and retrieves their information from the database.
# 7. Stores the student information in a list.
# 8. Counts the number of students and adds this information to the class entry.
# 9. Renders the 'view_class.html' template with the class entry and student data.
# 10. Returns an error message if the class is not found.
# 11. Redirects to the home page if the user is not logged in or does not have the correct user type.
@app.route('/view_class/<class_code>')
def view_class(class_code):
    if is_logged_in() and session.get('user_type') == 'teacher':
        db = testdb()
        accounts_db = accounts() 
        class_entry = db.find_one({'code': class_code})
        if class_entry:
            students = []
            for student_id in class_entry.get('students', []):
                student = accounts_db.find_one({'user_id': student_id})
                if student:
                    students.append({
                        'username': student.get('username'),
                        'email': student.get('email'),
                        'user_id': student.get('user_id')
                    })
            student_count = len(students)  
            class_entry['num_students'] = student_count  
            return render_template('view_class.html', class_entry=class_entry, students=students)
        return "Class not found", 404
    return redirect('/')

# This function handles the addition of a new test for a specific class.
# It performs the following steps:
# 1. Defines the route and method for the add_test function.
# 2. Checks if the user is logged in and if their user type is 'teacher'.
# 3. Retrieves the class code, test name, maximum mark, grading type, and test type from the submitted form data.
# 4. Initializes a dictionary to store grade boundaries if the grading type is 'boundaries'.
# 5. If the grading type is 'boundaries', populates the grade boundaries dictionary with the provided grade thresholds.
# 6. Connects to the database to retrieve the class entry based on the class code.
# 7. If the class entry is not found, returns a 404 error.
# 8. Retrieves the subject from the class entry.
# 9. Updates the class entry in the database to add the new test information:
#    - Includes subject, test name, test type, maximum mark, grading type, grade boundaries, and an empty dictionary for student marks.
# 10. Redirects to the view_class page with the class code.
# 11. Redirects to the home page if the user is not logged in or does not have the correct user type.
@app.route('/add_test', methods=['POST'])
def add_test():
    if is_logged_in() and session.get('user_type') == 'teacher':
        class_code = request.form['class_code']
        test_name = request.form['test_name']
        max_mark = request.form['max_mark']
        grading_type = request.form['grading_type']
        test_type=request.form['test_type']
        grade_boundaries = {}
        if grading_type == 'boundaries':
            grade_boundaries = {
                'A*': request.form.get('A_star', type=int),
                'A': request.form.get('A', type=int),
                'B': request.form.get('B', type=int),
                'C': request.form.get('C', type=int),
                'D': request.form.get('D', type=int),
                'E': request.form.get('E', type=int),
                'U': 0
            }
        db = testdb()
        class_entry = db.find_one({'code': class_code})
        if not class_entry:
            return "Class not found", 404
        subject = class_entry['subject']
        db.update_one(
            {'code': class_code},
            {
                '$push': {
                    'tests': {
                        'subject': subject,
                        'test_name': test_name,
                        'test_type':test_type,
                        'max_mark': max_mark,
                        'grading_type': grading_type,
                        'grade_boundaries': grade_boundaries,
                        'students_marks': {}
                    }
                }
            }
        )
        return redirect(url_for('view_class', class_code=class_code))
    return redirect('/')

# This function handles the process of adding marks for students in a specific class and test.
# It performs the following steps:
# 1. Defines the route and method for the add_marks function.
# 2. Checks if the user is logged in and if their user type is 'teacher'.
# 3. Connects to the databases to retrieve class and student information.
# 4. Retrieves the class entry based on the class code.
# 5. If the class entry is found, retrieves the list of students in the class.
# 6. Iterates through the list of students and retrieves their information from the database.
# 7. Stores the student information in a list.
# 8. Retrieves the test entry based on the test name.
# 9. If the test entry is not found, returns a 404 error.
# 10. Renders the 'add_marks.html' template with the class entry, students, and test entry.
# 11. Returns an error message if the class is not found.
# 12. Redirects to the home page if the user is not logged in or does not have the correct user type.
@app.route('/add_marks/<class_code>?=<test_name>')
def add_marks(class_code, test_name):
    if is_logged_in() and session.get('user_type') == 'teacher':
        db = testdb()
        accounts_db = accounts()
        class_entry = db.find_one({'code': class_code})
        if class_entry:
            students = []
            for student_id in class_entry.get('students', []):
                student = accounts_db.find_one({'user_id': student_id})
                if student:
                    students.append({
                        'user_id': student.get('user_id'),
                        'username': student.get('username'),
                        'email': student.get('email')
                    })
            test_entry = next((test for test in class_entry['tests'] if test['test_name'] == test_name), None)
            if not test_entry:
                return "Test not found", 404
            return render_template('add_marks.html', class_entry=class_entry, students=students, test_entry=test_entry)
        return "Class not found", 404
    return redirect('/')

# This function processes and submits student marks for a specific test in a class.
# It performs the following steps:
# 1. Checks if the user is logged in and if their user type is 'teacher'.
# 2. Retrieves the class code and test name from the submitted form data.
# 3. Converts the form data to a dictionary and prints the marks for debugging purposes.
# 4. Connects to the database to retrieve the class and test entries based on the class code and test name.
# 5. If the test entry is not found, returns a 404 error.
# 6. Retrieves the grading type and maximum mark for the test.
# 7. Initializes lists and dictionaries to store student scores and averages.
# 8. Iterates through the submitted marks and processes each student's mark:
#    - Retrieves and processes the student mark.
#    - Calculates the percentage based on the maximum mark.
#    - Updates the test entry with the student's mark and percentage.
#    - Stores the student's percentage in the scores and averages lists.
# 9. If the grading type is 'curve' and there are student scores, calculates average scores and grade boundaries.
# 10. Updates the database with the modified student marks in the test entry.
# 11. Redirects to the view_class page with the class code.
# 12. Redirects to the home page if the user is not logged in or does not have the correct user type.
@app.route('/submit_marks', methods=['POST'])
def submit_marks():
    if is_logged_in() and session.get('user_type') == 'teacher':
        class_code = request.form['class_code']
        test_name = request.form['test_name']
        marks = request.form.to_dict(flat=False)
        print(marks)
        db = testdb()
        class_entry = db.find_one({'code': class_code})
        test_entry = next((test for test in class_entry['tests'] if test['test_name'] == test_name), None)
        if not test_entry:
            return "Test not found", 404
        grading_type = test_entry.get('grading_type', 'boundaries') 
        max_mark = int(test_entry['max_mark'])
        student_scores = []
        student_averages = {}
        year = class_entry.get('year', 'N/A')
        for student_id, mark in marks.items():
            if student_id.startswith('marks['):
                student_id = student_id[6:-1]
                if mark and mark[0]:
                    mark = int(mark[0])  
                    percentage = round(((mark / max_mark) * 100), 1)
                    test_entry['students_marks'][student_id] = {'mark': mark, 'percentage': percentage}
                    student_scores.append(percentage)
                    student_averages[student_id] = percentage
        if grading_type == 'curve' and student_scores:
            subject = class_entry['subject']
            calculate_boundaries_and_graph(student_scores, subject, year, student_averages, session['school'], test_name=test_name)
        db.update_one(
            {'code': class_code, 'tests.test_name': test_name},
            {'$set': {'tests.$.students_marks': test_entry['students_marks']}}
        )
        return redirect(url_for('view_class', class_code=class_code))
    return redirect('/')

# This function handles the selection of a test for a specific class.
# It performs the following steps:
# 1. Defines the route and method for the select_test function.
# 2. Retrieves the test_name parameter from the query string in the request.
# 3. Redirects to the add_marks function, passing the class_code and test_name as arguments.

@app.route('/select_test/<class_code>', methods=['GET'])
def select_test(class_code):
    test_name = request.args.get('test_name')
    return redirect(url_for('add_marks', class_code=class_code, test_name=test_name))

# This function retrieves and processes performance data for a specific student in a given class.
# It performs the following steps:
# 1. Defines a dictionary for grade conversion from letter grades to numerical values for under Year 11 students.
# 2. Checks if the user is logged in and if their user type is 'teacher'.
# 3. Connects to the databases to retrieve class and student information.
# 4. Retrieves the class entry based on the class code.
# 5. If the class entry is found, retrieves the student's account information using the student_id.
# 6. If the student is found, processes their test marks:
#    - Iterates through each test in the class entry.
#    - Retrieves the student's mark and percentage for the test, initializing grade and image path.
#    - If the test has a percentage, processes the grade and image path based on the grading type.
#    - Assigns grades based on the grade boundaries if they exist.
#    - Converts grades to numerical values for under Year 11 students.
# 7. Appends the test information to the student's marks list.
# 8. Calculates the student's average percentage across all tests.
# 9. Renders the 'student_performance.html' template with the student data, marks, average percentage, and class entry.
# 10. Returns an error message if the class or student is not found.
# 11. Redirects to the home page if the user is not logged in or does not have the correct user type.s
@app.route('/student_performance/<class_code>/<student_id>')
def student_performance(class_code, student_id):
    GRADE_CONVERSION = {
        "A*": 9,
        "A": 8,
        "B": 7,
        "C": 6,
        "D": 5,
        "E": 4,
        "U": "U"
    }

    if is_logged_in() and session.get('user_type') == 'teacher':
        db = testdb()
        accounts_db = accounts()
        class_entry = db.find_one({'code': class_code})
        if class_entry:
            student = accounts_db.find_one({'user_id': student_id})
            if student:
                student_marks = []
                total_percentage = 0
                test_count = 0      
                for test in class_entry.get('tests', []):
                    mark_entry = test['students_marks'].get(student_id, {'mark': 'X', 'percentage': 0})
                    percentage = round(mark_entry['percentage'], 2) if mark_entry['mark'] != 'X' else 'X'
                    grade = 'N/A'
                    image_path = None
                    grade_boundaries = {}
                    if percentage != 'X':
                        if test['grading_type'] == 'curve':
                            grade_boundaries = test.get('grade_boundaries', {})
                            school_name=session['school']
                            image_path = f'/static/subject_years/{school_name}/{class_entry["subject"]}-Y{class_entry["year"]}/{test["test_name"]}.png'
                        else:
                            grade_boundaries = test.get('grade_boundaries', {})
                        if grade_boundaries:
                            for grade_letter, boundary in sorted(grade_boundaries.items(), key=lambda x: x[1], reverse=True):
                                if percentage >= boundary:
                                    grade = grade_letter
                                    break
                        
                        if int(class_entry['year']) <= 11 and grade in GRADE_CONVERSION:
                            grade = GRADE_CONVERSION[grade]
                    if int(class_entry['year']) <= 11:
                        grade_boundaries = {GRADE_CONVERSION[grade]: boundary for grade, boundary in grade_boundaries.items()}
                    student_marks.append({
                        'test_name': test['test_name'],
                        'test_type': test['grading_type'].title(),
                        'percentage': percentage,
                        'grade': grade,
                        'image_path': image_path,
                        'grade_boundaries': grade_boundaries
                    })

                    if mark_entry['mark'] != 'X':
                        total_percentage += mark_entry['percentage']
                        test_count += 1
                average_percentage = round(total_percentage / test_count, 2) if test_count > 0 else 0
                return render_template(
                    'student_performance.html',
                    student=student,
                    student_marks=student_marks,
                    average_percentage=average_percentage,
                    class_entry=class_entry,
                    class_code=class_code
                )
        return "Class or student not found", 404
    return redirect('/')

# This function retrieves and processes test data for a specific class for a student.
# It performs the following steps:
# 1. Checks if the user is logged in and if their user type is 'student'.
# 2. Connects to the database to retrieve class information based on the class code.
# 3. Extracts the student_id from the session.
# 4. Checks if the class entry exists and if the student is enrolled in the class.
# 5. Initializes a list to store test information and extracts the year and subject from the class entry.
# 6. Iterates through each test in the class entry:
#    - Retrieves the student's mark and percentage for the test.
#    - Initializes the grade as 'N/A' and the image path as None.
#    - If the test has a percentage, processes the grade and image path based on the grading type.
#    - Assigns grades based on the grade boundaries if they exist.
# 7. Adds the test information to the list.
# 8. Renders the 'class_tests.html' template with the class entry and test data.
# 9. Returns an error message if the class is not found or the student is not enrolled in the class.
# 10. Redirects to the home page if the user is not logged in or does not have the correct user type.
@app.route('/class_tests/<class_code>')
def class_tests(class_code):
    if is_logged_in() and session.get('user_type') == 'student':
        db = testdb()
        class_entry = db.find_one({'code': class_code})
        student_id = session['user_id']
        if class_entry and 'students' in class_entry and student_id in class_entry['students']:
            tests = []
            year = class_entry.get('year', 'N/A')
            subject = class_entry.get('subject', 'N/A')
            subject_year = f"{subject}-Y{year}"
            for test in class_entry.get('tests', []):
                student_mark = test['students_marks'].get(student_id, {'mark': 'N/A', 'percentage': 'N/A'})
                percentage = student_mark['percentage']
                grade = 'N/A'
                image_path = None
                grade_boundaries = test.get('grade_boundaries', {})
                if percentage != 'N/A':
                    if test['grading_type'] == 'curve':
                        school_name=session['school']
                        image_path = f'/static/subject_years/{school_name}/{subject_year}/{test["test_name"]}.png' 
                        grade_boundaries_entry = class_entry['tests'][0].get('grade_boundaries')
                        if grade_boundaries_entry:
                            grade_boundaries = grade_boundaries_entry
                    if grade_boundaries:
                        for grade_letter, boundary in sorted(grade_boundaries.items(), key=lambda x: x[1], reverse=True):
                            if percentage >= boundary:
                                grade = grade_letter
                                break   
                tests.append({
                    'subject': test['subject'],
                    'test_name': test['test_name'],
                    'percentage': percentage,
                    'grading_type': test['grading_type'].title(),
                    'grade': grade,
                    'image_path': image_path,
                    'grade_boundaries': grade_boundaries
                })
            return render_template('class_tests.html', class_entry=class_entry, tests=tests)
        return "Class not found or you are not enrolled in this class", 404
    return redirect('/')


# This function updates the grades and average percentages of a student for a given class.
# It performs the following steps:
# 1. Connects to the database.
# 2. Iterates through each test in the class entry.
# 3. Checks if the student has marks for the test.
# 4. Retrieves the percentage of marks the student obtained in the test.
# 5. Initializes the grade as 'N/A'.
# 6. If the test uses grade boundaries, assigns a grade based on the student's percentage.
# 7. Updates the student's average percentage and grade for the subject in the database.
#    - Uses the student_id and the subject to find the document.
#    - Sets the average percentage and grade in the document, using the upsert option to insert if it does not exist.
def update_student_grades_and_averages(student_id, class_entry):
    db = testdb()
    for test in class_entry.get('tests', []):
        if student_id in test['students_marks']:
            percentage = test['students_marks'][student_id]['percentage']
            subject = test['subject']
            grade = 'N/A'
            if test['grading_type'] == 'boundaries':
                for grade_letter, boundary in test['grade_boundaries'].items():
                    if percentage >= boundary:
                        grade = grade_letter
                        break
            db.update_one(
                {'_id': student_id, 'subjects.subject': subject},
                {'$set': {'subjects.$.average_percentage': percentage, 'subjects.$.grade': grade}},
                upsert=True
            )

# This function retrieves and processes test data for a specific subject and year for a student.
# It performs the following steps:
# 1. Checks if the user is logged in and if their user type is 'student'.
# 2. Connects to the database to retrieve class information based on the subject and year.
# 3. Extracts the student_id from the session.
# 4. Splits the subject_year string to get the subject and year.
# 5. Retrieves the classes that the student is part of for the given subject and year.
# 6. Initializes a list to store test information and variables for total percentage and test count.
# 7. Iterates through each class entry and its tests to find the student's test scores.
#    - If the test matches the subject and includes the student's marks, it adds the test information to the list.
#    - Accumulates the total percentage and increments the test count.
# 8. Calculates the average percentage of the student's test scores.
# 9. Constructs the image path for the subject year.
# 10. Renders the 'subject_tests.html' template with the test data, average percentage, and image path.
# 11. Redirects to the home page if the user is not logged in or does not have the correct user type.
@app.route('/subject_tests/<subject_year>')
def subject_tests(subject_year):
    if is_logged_in() and session.get('user_type') == 'student':
        db = testdb()
        student_id = session['user_id']
        subject, year = subject_year.split('-Y')
        classes = list(db.find({'students': student_id, 'subject': subject, 'year': year}))
        tests = []
        total_percentage = 0
        test_count = 0
        for class_entry in classes:
            for test in class_entry.get('tests', []):
                if test['subject'] == subject and student_id in test['students_marks']:
                    percentage = test['students_marks'][student_id]['percentage']
                    total_percentage += percentage
                    test_count += 1
                    test_info = {
                        'test_name': test['test_name'],
                        'percentage': percentage
                    }
                    tests.append(test_info)
        average_percentage = round(total_percentage / test_count, 2) if test_count > 0 else 0
        school_name=session['school']
        image_path = f'/static/subject_years/{school_name}/{subject_year}/{subject_year}.png' 
        return render_template('subject_tests.html', subject_year=subject_year, tests=tests, average_percentage=average_percentage, image_path=image_path)
    return redirect('/')

# This function ensures that grade boundaries for a given class are updated in the database.
# It performs the following steps:
# 1. Constructs a subject_year string from the class's subject and year.
# 2. Retrieves the list of tests from the class entry.
# 3. Iterates through each test entry in the list.
# 4. Checks if grade boundaries exist for the test.
# 5. If grade boundaries are found, updates the grade boundaries in the database.
#    - Uses the subject_year and a None test_name to find or create the document.
#    - Sets the grade boundaries in the document, using the upsert option to insert if it does not exist.
def ensure_grade_boundaries(db, class_entry):
    subject_year = f"{class_entry['subject']}-Y{class_entry['year']}"
    test_entries = class_entry.get('tests', [])
    
    for test in test_entries:
        grade_boundaries = test.get('grade_boundaries')
        if grade_boundaries:
            db.update_one(
                {'subject_year': subject_year, 'test_name': None},
                {'$set': {'grade_boundaries': grade_boundaries}},
                upsert=True
            )

#--done--
# This function retrieves and processes class data for a given class code.
# It performs the following steps:
# 1. Checks if the user is logged in and if they have the correct user type (admin or teacher).
# 2. Connects to the database to retrieve class information based on the class code.
# 3. If the class is not found, it prints an error message and returns a 404 error.
# 4. Ensures grade boundaries are set for the class.
# 5. Retrieves grade boundaries for the class's subject and year.
# 6. Defines a function to assign grades based on percentage and grade boundaries.
# 7. If grade boundaries are found, processes student data:
#     - Retrieves student information and initializes their marks and grades.
#     - Processes test scores and assigns grades to students based on their percentages.
#     - Calculates the class total and average percentages.
#     - Calculates the school average percentage and class rank.
# 8. Prepares the response data, including class entry, students, tests, and averages.
# 9. Renders the response using the 'class_data.html' template.
# 10. If grade boundaries are not found, returns a 404 error.
# 11. Redirects to the home page if the user is not logged in or does not have the correct user type.
@app.route('/class_data/<class_code>')
def class_data(class_code):
    if is_logged_in() and session.get('user_type') in ['admin', 'teacher']:
        db = testdb()
        class_entry = db.find_one({'code': class_code})
        if not class_entry:
            print(f"Class not found for code: {class_code}")
            return "Class not found", 404

        ensure_grade_boundaries(db, class_entry)

        subject_year = f"{class_entry['subject']}-Y{class_entry['year']}"

        grade_boundaries_entry = db.find_one({'subject_year': subject_year, 'test_name': None})

        def assign_grade(percentage, grade_boundaries):
            for grade_letter, boundary in sorted(grade_boundaries.items(), key=lambda x: x[1], reverse=True):
                if percentage >= boundary:
                    return grade_letter
            return 'U'
        
        if grade_boundaries_entry:
            grade_boundaries = grade_boundaries_entry['grade_boundaries']
            students = {}
            for student_id in class_entry.get('students', []):
                student_doc = accounts().find_one({'user_id': student_id})
                if student_doc:
                    students[student_id] = {
                        'username': student_doc['username'],
                        'marks': {},
                        'average_percentage': 0,
                        'grade': 'N/A'
                    }
            tests = class_entry.get('tests', [])
            for test in tests:
                for student_id, marks in test.get('students_marks', {}).items():
                    if student_id in students:
                        percentage = marks['percentage']
                        students[student_id]['marks'][test['test_name']] = percentage
                        grade = assign_grade(percentage, grade_boundaries)
                        students[student_id]['marks'][f"{test['test_name']}_grade"] = grade

            class_total_percentage = 0
            class_total_students = 0
            for student_id, student_data in students.items():
                numeric_marks = [value for value in student_data['marks'].values() if isinstance(value, (int, float))]
                if numeric_marks:
                    test_percentage = sum(numeric_marks) / len(numeric_marks)
                    student_data['average_percentage'] = round(test_percentage, 1)
                    student_data['grade'] = assign_grade(student_data['average_percentage'], grade_boundaries)
                    class_total_percentage += student_data['average_percentage']
                    class_total_students += 1

            class_average_percentage = round(class_total_percentage / class_total_students, 1) if class_total_students > 0 else 0
            school_average_percentage = class_average_percentage
            class_averages = [class_average_percentage]
            sorted_class_averages = sorted(class_averages, reverse=True)
            class_rank = sorted_class_averages.index(class_average_percentage) + 1 if class_average_percentage in sorted_class_averages else 'N/A'
            response = {
                'class_entry': class_entry,
                'students': students,
                'tests': tests,
                'class_average_percentage': class_average_percentage,
                'school_average_percentage': school_average_percentage,
                'class_rank': class_rank,
                'school_name': session['school']
            }
            return render_template('class_data.html', data=response)
        else:
            return "Grade boundaries not found", 404
    return redirect('/')

# This function generates a PDF report for a student's performance.
# It performs the following steps:
# 1. Sets up a dictionary for grade conversion from letter grades to numerical values.
# 2. Creates an in-memory buffer to store the PDF data.
# 3. Initializes the PDF document with landscape orientation and A4 page size.
# 4. Prepares styles for the title and normal text.
# 5. Connects to the databases to retrieve student information and test data.
# 6. Retrieves the student's account information using the provided student_id.
# 7. If the student is not found, returns None.
# 8. Adds the report title and the student's email to the PDF elements.
# 9. Retrieves all classes the student is part of and initializes a dictionary to store subjects and years.
# 10. Iterates through each class and its tests to calculate the student's performance percentages.
# 11. Calculates the average percentage for each subject and year combination.
# 12. Defines a function to assign grades based on the calculated percentages and grade boundaries.
# 13. Assigns grades for each subject and year based on the average percentages.
# 14. Creates tables for each subject and year with the student's test scores and calculated grades.
# 15. Adds the tables to the PDF elements, ensuring a structured layout.
# 16. Builds the PDF document with all the prepared elements.
# 17. Resets the buffer position to the beginning and returns the PDF data as a byte string.
def generate_student_report(student_id):
    GRADE_CONVERSION = {
        "A*": 9,
        "A": 8,
        "B": 7,
        "C": 6,
        "D": 5,
        "E": 4,
        "U": "U"
    }
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    elements = []
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    normal_style = styles['Normal']
    db = testdb()
    accounts_db = accounts()
    student = accounts_db.find_one({'user_id': student_id})
    if not student:
        return None
    title = Paragraph(f"Performance Report for {student['username']}", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))
    email = Paragraph(f"Email: {student['email']}", normal_style)
    elements.append(email)
    elements.append(Spacer(1, 12))
    classes = list(db.find({'students': student_id}))
    subjects_years = {}
    for class_entry in classes:
        year = class_entry.get('year', 'N/A')
        for test in class_entry.get('tests', []):
            if student_id in test['students_marks']:
                percentage = test['students_marks'][student_id]['percentage']
                subject = test['subject']
                subject_year = f"{subject}-Y{year}"
                if subject_year not in subjects_years:
                    subjects_years[subject_year] = {'total_percentage': 0, 'count': 0}
                subjects_years[subject_year]['total_percentage'] += percentage
                subjects_years[subject_year]['count'] += 1
    for subject_year in subjects_years:
        subjects_years[subject_year]['average_percentage'] = round(
            subjects_years[subject_year]['total_percentage'] / subjects_years[subject_year]['count'], 1)
    def assign_grade(percentage, grade_boundaries):
        for grade_letter, boundary in sorted(grade_boundaries.items(), key=lambda x: x[1], reverse=True):
            if percentage >= boundary:
                if int(class_entry['year']) <= 11:
                    return GRADE_CONVERSION[grade_letter]
                return grade_letter
        return 'U'
    for subject_year in subjects_years:
        subject, year = subject_year.split('-Y')
        grade_boundaries = db.find_one({'subject_year': subject_year, 'test_name': None}, {'grade_boundaries': 1, '_id': 0})
        if grade_boundaries:
            grade_boundaries = grade_boundaries.get('grade_boundaries', {})
            average_percentage = subjects_years[subject_year]['average_percentage']
            grade = assign_grade(average_percentage, grade_boundaries)
            subjects_years[subject_year]['grade'] = grade
        else:
            subjects_years[subject_year]['grade'] = 'N/A'
    column_width = 4.5 * inch
    row_tables = []
    for subject_year, values in subjects_years.items():
        subject, year = subject_year.split('-Y')
        data = [["Class", "Year", "Test Name", "Percentage", "Grade"]]
        for class_entry in classes:
            if class_entry.get('subject') == subject and class_entry.get('year') == year:
                class_name = class_entry.get('classname', 'N/A')
                for test in class_entry.get('tests', []):
                    if student_id in test['students_marks']:
                        student_mark = test['students_marks'][student_id]
                        percentage = student_mark['percentage']
                        grade_boundaries = test.get('grade_boundaries', {})
                        grade = assign_grade(percentage, grade_boundaries)
                        data.append([class_name, year, test['test_name'], f"{percentage}%", grade])
        data.append(["Average", year, "", f"{values['average_percentage']}%", values['grade']])
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),  
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), 
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), 
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.lightgreen, colors.whitesmoke]),  
            ('GRID', (0, 0), (-1, -1), 1, colors.black), 
        ]))
        subject_title = Paragraph(f"Subject: {subject}", title_style)
        year_title = Paragraph(f"Year: {year}", normal_style)
        row_tables.append([subject_title, Spacer(1, 6), year_title, Spacer(1, 12), table])
    for i in range(0, len(row_tables), 2):
        row = []
        for j in range(2):
            if i + j < len(row_tables):
                row.append(row_tables[i + j])
        elements.append(Table([row], colWidths=[column_width] * len(row)))
        elements.append(Spacer(1, 12))
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

# This function generates a report for a specific student in PDF format.
# It verifies if the user is logged in and if they are an admin or the student themselves.
# If the student is found, it returns the PDF file as a response.
# If the student is not found, it returns a 404 error.
@app.route('/generate_report/<student_id>')
def generate_report(student_id):
    if is_logged_in() and session.get('user_type') in ['admin', 'student']:
        pdf_data = generate_student_report(student_id)
        if pdf_data:
            return Response(pdf_data, mimetype='application/pdf', headers={"Content-Disposition": f"attachment; filename=report_{student_id}.pdf"})
        return "Student not found", 404
    return redirect('/')

#--Done--
# This function handles the upload of a CSV file containing user data.
# It verifies if the user is logged in and if they are an admin.
# If the file is missing, it redirects to the home page.
# It processes the CSV file and adds the users to the database, avoiding duplicates.
# It addes all exsisting users to session to be returned to admin homepage
@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    if is_logged_in() and session.get('user_type') == 'admin':
        if 'file' not in request.files:
            return redirect('/')
        file = request.files['file']
        if file.filename == '':
            return redirect('/')
        if file and file.filename.endswith('.csv'):
            db = accounts()
            school = session['school']
            reader = csv.DictReader(file.read().decode('utf-8').splitlines())
            existing_users = []
            for row in reader:
                username = row['name']
                password = generate_password_hash(row['password'])
                email = row['email']
                user_type = row['account_type']
                user_id = str(uuid.uuid4())
                existing_user = db.find_one({'username': username, 'school': school})
                if existing_user:
                    existing_users.append(username)
                    continue
                user = {
                    'user_id': user_id,
                    'username': username,
                    'email': email,
                    'password': password,
                    'school': school,
                    'type': user_type
                }
                db.insert_one(user)
            session['existing_users'] = existing_users
            return redirect('/')
    return redirect('/')

#--Done--
# This Flask function handles 404 errors, which occur when a requested page 
# is not found on the server. When such an error happens, the function captures 
# it and responds by rendering a custom HTML template, '404.html', to inform 
# the user about the missing page. The function returns the rendered template 
# along with a 404 status code, signaling to the browser that the page was not found.
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

#--Done--
# This function handles the logout process for a user.
# It clears all session data, effectively logging the user out,
# and then redirects the user to the home page.
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

#--Done--
# This condition ensures that the script runs only if it is executed directly,
# and not when it is imported as a module.
if __name__ == "__main__":
    app.run(debug=True)
