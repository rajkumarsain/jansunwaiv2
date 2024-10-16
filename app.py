from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
import os
import logging
from flask import send_from_directory
from datetime import datetime
import time
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

app = Flask(__name__)

# Update the database URI to use MySQL
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://jansunwai_user:Doit1234@localhost/jansunwai'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads/'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
migrate = Migrate(app, db)

# Ensure the uploads directory exists
if not os.path.exists('uploads'):
    os.makedirs('uploads')

# Modify the relationship in User and Department model to lazy='dynamic'
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    #department = db.relationship('Department', backref='users', lazy='select')


class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    questions = db.relationship('Question', backref='department', lazy=True)
    users = db.relationship('User', backref='department', lazy=True)

# Question model
class Question(db.Model):
    id = db.Column(db.String(10), primary_key=True)  # Custom ID field (MMDDYYXXXX format)
    question = db.Column(db.String(500), nullable=False)
    file = db.Column(db.String(200))  # Optional file attachment
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)  # Link to Department
    replies = db.relationship('Reply', backref='question', lazy=True)  # Add relationship to replies
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())  # Add timestamp column

# Reply model
class Reply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reply = db.Column(db.String(500), nullable=False)
    file = db.Column(db.String(200))  # Optional file attachment
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())  # Add timestamp for when the reply was created

#file models to hold attachments in upload folder
class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(200), nullable=False)  # The name of the file
    file_path = db.Column(db.String(500), nullable=False)  # The path where the file is stored
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=True)  # Reference to Question
    reply_id = db.Column(db.Integer, db.ForeignKey('reply.id'), nullable=True)  # Reference to Reply
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)  # Reference to Department
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())  # Timestamp

    # Relationships (optional for easier access)
    question = db.relationship('Question', backref='files')
    reply = db.relationship('Reply', backref='files')
    department = db.relationship('Department', backref='files')

def create_default_users():
    # Check if the admin user already exists, and create it if not
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', password='admin123', is_admin=True)
        db.session.add(admin_user)
        db.session.commit()

def create_default_departments():
    if not Department.query.first():
        departments = ['DOITC', 'JVVNL', 'DFO', 'PHED']  # Add your department names
        for name in departments:
            new_department = Department(name=name)
            db.session.add(new_department)
        db.session.commit()

# Function to load user based on user_id
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))  # Redirect to admin dashboard if admin
        else:
            return redirect(url_for('department_dashboard'))  # Redirect to user dashboard if not admin
    return render_template('base.html')  # If not logged in, show the base template


# Route to show department summary on the department's dashboard
@app.route('/department/dashboard')
@login_required
def department_dashboard():
    if current_user.department_id:
        # Get all questions assigned to this user's department
        department_id = current_user.department_id
        questions = Question.query.filter_by(department_id=department_id).all()

        # Calculate the total assigned and pending questions
        total_assigned = len(questions)
        total_pending = len([q for q in questions if not q.replies])  # Questions without replies

        return render_template(
            'department_dashboard.html',
            total_assigned=total_assigned,
            total_pending=total_pending
        )
    else:
        flash("No department assigned to this user.", "danger")
        return redirect(url_for('index'))

# login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            login_user(user)

            # Redirect based on user role
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('department_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Admin routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        return redirect(url_for('department_dashboard'))

    # Fetch all departments and questions
    departments = Department.query.all()
    
    departments_summary = []
    for department in departments:
        # Count total questions assigned to the department
        question_count = Question.query.filter_by(department_id=department.id).count()
        
        # Count pending questions (questions with no replies yet)
        pending_count = Question.query.outerjoin(Reply).filter(
            Question.department_id == department.id, Reply.id.is_(None)
        ).count()
        
        departments_summary.append((department, question_count, pending_count))

    questions = Question.query.all()
    
    return render_template('admin_dashboard.html', questions=questions, departments_summary=departments_summary)

#route for add question
from datetime import datetime
from werkzeug.utils import secure_filename
import os

@app.route('/admin/add_question', methods=['GET', 'POST'])
@login_required
def add_question():
    if not current_user.is_admin:
        return redirect(url_for('view_questions_by_department'))
    
    departments = Department.query.all()  # Fetch all departments
    
    if request.method == 'POST':
        question_text = request.form['question']
        department_id = request.form['department']  # Get selected department
        files = request.files.getlist('files')  # Get all uploaded files

        # Generate custom ID in MMDDYY format
        today = datetime.now().strftime('%m%d%y')  # MMDDYY format
        # Get the number of questions created today to generate the serial number
        questions_today_count = Question.query.filter(Question.id.like(f"{today}%")).count() + 1
        custom_id = f"{today}{questions_today_count:04d}"  # MMDDYYXXXX format

        # Create a new question record with the generated custom ID
        new_question = Question(id=custom_id, question=question_text, department_id=department_id)
        db.session.add(new_question)
        db.session.commit()

        # Process each file, save it, and create File records
        for file in files:
            if file and file.filename:  # Check if a file was uploaded
                # Generate a secure filename
                filename = secure_filename(f"{new_question.id}_{file.filename}")
                file_path = os.path.join(app.config['UPLOAD'], filename)
                file.save(file_path)

                # Create a new File record for each uploaded file
                new_file = File(file_name=file.filename, file_path=file_path, question_id=new_question.id, department_id=department_id)
                db.session.add(new_file)

        db.session.commit()  # Commit all changes to the database
        
        flash('Question and files submitted successfully!', 'success')  # Flash success message
        return redirect(url_for('add_question'))
    
    return render_template('add_question.html', departments=departments)


# Serve uploaded files from the 'uploads' folder
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

#view_reply_question_user to fetch questions and replies
@app.route('/view_questions_by_user', methods=['GET', 'POST'])
@login_required
def view_questions_by_user():
    # Fetch questions assigned to the user's department
    if current_user.department_id:
        questions = Question.query.filter_by(department_id=current_user.department_id).all()
    else:
        questions = []

    # Check if there are replies for each question and get files associated with replies
    for question in questions:
        question.replies = Reply.query.filter_by(question_id=question.id).all()

        # Fetch files related to the question and replies
        for reply in question.replies:
            reply.files = File.query.filter_by(reply_id=reply.id).all()

    # Handle form submissions for replies
    if request.method == 'POST':
        reply_text = request.form['reply']
        question_id = request.form['question_id']  # Assuming question ID is passed with the form
        file = request.files.get('file')

        # Create new reply
        new_reply = Reply(reply=reply_text, question_id=question_id, user_id=current_user.id)
        db.session.add(new_reply)
        db.session.commit()

        # If a file is uploaded, save it and associate it with the reply
        if file:
            original_filename = secure_filename(file.filename)
            # Generate a unique filename using question_id and timestamp
            unique_filename = f"{question_id}_{int(time.time())}_{original_filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)

            # Save the file info in the database
            new_file = File(file_name=original_filename, file_path=unique_filename,
                            question_id=question_id, reply_id=new_reply.id, department_id=current_user.department_id)
            db.session.add(new_file)
            db.session.commit()

        flash('Reply and file submitted successfully!', 'success')

    return render_template('view_questions_by_user.html', questions=questions)

#will display the details of a specific qustion and provide an option to reply
@app.route('/user/question/<int:question_id>', methods=['GET', 'POST'])
@login_required
def reply_to_question(question_id):
    question = Question.query.get_or_404(question_id)
    replies = Reply.query.filter_by(question_id=question_id).all()

    if request.method == 'POST':
        reply_text = request.form['reply']
        file = request.files.get('file')
        filename = secure_filename(file.filename) if file else None

        if filename:
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_reply = Reply(reply=reply_text, file=filename, question_id=question_id, user_id=current_user.id)
        db.session.add(new_reply)
        db.session.commit()

        flash("Reply submitted successfully", "success")
        return redirect(url_for('reply_to_question', question_id=question_id))

    return render_template('reply_to_question.html', question=question, replies=replies)

#view questions department wise by admin 
@app.route('/questions', methods=['GET'])
@login_required
def view_questions_by_admin():
    # Get the department_id from the current user's session (for department-specific login)
    if not current_user.is_admin and current_user.department_id:
        # If the current user is not an admin, show only their department's questions
        department_id = current_user.department_id
        departments = Department.query.filter_by(id=department_id).all()  # Only show their department in the dropdown
        questions = Question.query.filter_by(department_id=department_id).all()
        selected_department_id = department_id
    else:
        # Admin case: fetch department_id from the query string for filtering
        department_id = request.args.get('department_id', 'all')
        departments = Department.query.all()  # Admin can see all departments

        if department_id == "all":
            questions = Question.query.all()
            selected_department_id = "all"
        else:
            questions = Question.query.filter_by(department_id=department_id).all()
            selected_department_id = int(department_id)

    return render_template(
        'view_questions_by_admin.html',
        departments=departments,
        questions=questions,
        selected_department_id=selected_department_id
    )

#user creation
# Route for admin to add a department-specific user
@app.route('/admin/add_user', methods=['GET', 'POST'])
@login_required
def add_user():
    if not current_user.is_admin:
        return redirect(url_for('department_dashboard'))

    departments = Department.query.all()

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        department_id = request.form['department']
        is_admin = bool(request.form.get('is_admin', False))  # Admin checkbox

        # Check if the username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists!', 'danger')
            return render_template('add_user.html', departments=departments)  # Render the template without redirect to avoid multiple flashes

        # Add new user if username does not exist
        new_user = User(username=username, password=password, department_id=department_id, is_admin=is_admin)
        db.session.add(new_user)
        db.session.commit()
        flash('User added successfully!', 'success')
        return redirect(url_for('add_user'))

    return render_template('add_user.html', departments=departments)


# Route to view the list of users
@app.route('/admin/view_users', methods=['GET'])
@login_required
def view_users():
    if not current_user.is_admin:
        return redirect(url_for('department_dashboard'))
    
    users = User.query.all()  # Fetch all users
    return render_template('view_user.html', users=users)
#Route to update user details
@app.route('/admin/update_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def update_user(user_id):
    if not current_user.is_admin:
        return redirect(url_for('department_dashboard'))

    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        new_username = request.form['username']
        new_password = request.form['password']

        # Check if the new username already exists (but ignore the current user's username)
        existing_user = User.query.filter(User.username == new_username, User.id != user.id).first()

        if existing_user:
            flash('Username already exists!', 'danger')
            return render_template('update_user.html', user=user)

        # Validate that password is not empty
        if not new_password:
            flash('Password cannot be empty!', 'danger')
            return render_template('update_user.html', user=user)

        # Update user details
        user.username = new_username
        user.password = new_password  # Ensure the password is updated
        
        db.session.commit()

        flash('User updated successfully!', 'success')
        return redirect(url_for('view_users'))

    return render_template('update_user.html', user=user)


#add department
@app.route('/admin/add_department', methods=['GET', 'POST'])
@login_required
def add_department():
    if not current_user.is_admin:
        return redirect(url_for('department_dashboard'))
    
    if request.method == 'POST':
        department_name = request.form['department_name']

        # Check if department already exists
        existing_department = Department.query.filter_by(name=department_name).first()
        if existing_department:
            flash('Department already exists!', 'danger')
        else:
            # Add new department
            new_department = Department(name=department_name)
            db.session.add(new_department)
            db.session.commit()
            flash('Department added successfully!', 'success')
        
        return redirect(url_for('add_department'))  # Avoid redirect to other route, stay on form page.

    return render_template('add_department.html')


#view departments
@app.route('/admin/departments', methods=['GET'])
@login_required
def view_departments():
    if not current_user.is_admin:
        return redirect(url_for('department_dashboard'))
    
    departments = Department.query.all()  # Fetch all departments
    return render_template('view_departments.html', departments=departments)

#update department details
@app.route('/admin/update_department/<int:department_id>', methods=['GET', 'POST'])
@login_required
def update_department(department_id):
    if not current_user.is_admin:
        return redirect(url_for('department_dashboard'))
    
    department = Department.query.get_or_404(department_id)
    
    if request.method == 'POST':
        new_name = request.form['department_name']
        
        # Check for duplicate department name
        existing_department = Department.query.filter(Department.name == new_name, Department.id != department.id).first()
        if existing_department:
            flash('Department name already exists!', 'danger')
            return render_template('update_department.html', department=department)

        # Update department name
        department.name = new_name
        db.session.commit()

        flash('Department updated successfully!', 'success')
        return redirect(url_for('view_departments'))

    return render_template('update_department.html', department=department)


#To handle replies for each question:
@app.route('/add_reply/<int:question_id>', methods=['POST'])
@login_required
def add_reply(question_id):
    question = Question.query.get_or_404(question_id)
    
    reply_text = request.form['reply']
    file = request.files.get('file')
    filename = None

    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    # Add the new reply
    new_reply = Reply(reply=reply_text, file=filename, question_id=question_id, user_id=current_user.id)
    db.session.add(new_reply)
    db.session.commit()
    
    return redirect(url_for('department_dashboard'))

#view department summary on department login
@app.route('/user/department_summary')
@login_required
def department_summary():
    if current_user.department_id:
        # Fetch all questions assigned to the current user's department
        questions = Question.query.filter_by(department_id=current_user.department_id).all()

        # Compute the total number of assigned questions
        total_assigned = len(questions)

        # Compute the total number of pending questions (no replies)
        total_pending = 0
        for question in questions:
            if Reply.query.filter_by(question_id=question.id).count() == 0:
                total_pending += 1
    else:
        total_assigned = 0
        total_pending = 0

    return render_template(
        'department_summary.html',  # Name of the template
        total_assigned=total_assigned,
        total_pending=total_pending
    )

#main
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Creates the tables if they don't exist
        create_default_users()  # Populate the database with default admin and client users
        create_default_departments()  # Populate the database with default departments
    app.run(debug=True)