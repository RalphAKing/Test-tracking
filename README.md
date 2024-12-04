# CSTMS - Comprehensive School Test Management System

## Overview

This is for a school project

CSTMS is a web-based application for managing school tests, student grades, and academic performance. It allows administrators, teachers, and students to interact with the system in different ways:

- **Admins** can upload student data, manage users, and view detailed reports.
- **Teachers** can manage test data, grade students, and calculate class averages.
- **Students** can view their test results, grades, and download performance reports.

The system is built using **Flask**, **MongoDB**, and **HTML/CSS** for the web interface.

## Features

- **Test Management**: Teachers can create, grade, and manage tests for students.
- **Student Grades**: Grades are calculated based on percentage thresholds (boundaries) and can be customized.
- **Performance Reports**: Students can generate and download PDF reports showing their grades and performance.
- **CSV Upload**: Admins can upload a CSV file to add multiple students to the system at once.
- **Class and Subject Management**: Teachers and admins can view class and subject data, including individual student performance and class averages.

## Installation

### Requirements

- Python 3.x
- Flask
- PyMongo (for MongoDB interaction)
- ReportLab (for PDF generation)
- MongoDB (local or cloud)

### Steps to Install

1. **Clone the repository**:

   ```bash
   git clone <repository_url>
   cd CSTMS
   ```

2. **Set up a virtual environment** (recommended):

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows, use 'venv\Scripts\activate'
   ```

3. **Install required Python packages**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up MongoDB**:
   - Make sure MongoDB is running locally or on a cloud service.
   - Create a database for CSTMS, or configure the connection string if using a cloud database.

5. **Run the application**:

   ```bash
   python app.py
   ```

6. Access the app in your web browser at `http://127.0.0.1:5000/`.

## Usage

### User Types

1. **Admin**:
   - Upload CSV files with student information.
   - Add or remove users and manage their roles.
   - View and manage grade boundaries, subjects, and tests.
   - Generate and download student performance reports.

2. **Teacher**:
   - Create and grade tests.
   - View class and subject performance.
   - Manage students' grades based on their test scores.

3. **Student**:
   - View and track personal test scores.
   - Check average scores and grades.
   - Download a detailed performance report (PDF).

### Routes

- `/login`: Login page for all users.
- `/logout`: Logs out the current user.
- `/subject_tests/<subject_year>`: View tests and grades for a particular subject and year.
- `/class_data/<class_code>`: View detailed data and grades for a class.
- `/generate_report/<student_id>`: Generate and download the student's performance report.
- `/upload_csv`: Admin-only route to upload a CSV file containing user data.
- `/`: Home page (requires login).

### Grade Conversion

Grades are converted using the following scale:

- **A*** = 9
- **A** = 8
- **B** = 7
- **C** = 6
- **D** = 5
- **E** = 4
- **U** = Unclassified

Grade boundaries can be customized for each test and are stored in the database.

### PDF Report

Performance reports are generated using the **ReportLab** library and are made available in PDF format. The report includes:

- Personal information (username, email).
- Test results (class, year, test name, percentage, and grade).
- Average score per subject.

## Example CSV Format

Here’s an example of how the CSV file for student uploads should be formatted:

```csv
name,email,account_type,school,password
John Doe,john.doe@example.com,student,ABC_School,hashed_password
Jane Smith,jane.smith@example.com,teacher,ABC_School,hashed_password
```

- **name**: Full name of the student or teacher.
- **email**: Email address.
- **account_type**: Type of account (`student`, `teacher`, `admin`).
- **school**: The name of the school.
- **password**: The password for the user, hashed before uploading.

## Upcoming changes / additions 

1. C# script to intergrate with sims markbook to automaticaly update the data
2. An api to allow external tools to use the system

## Contributing

Contributions to the CSTMS project are welcome.