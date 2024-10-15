from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
import os
import logging

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
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False)
    file = db.Column(db.String(200))  # Optional file attachment
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)  # Link to Department
    replies = db.relationship('Reply', backref='question', lazy=True)  # Add relationship to replies

# Reply model
class Reply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reply = db.Column(db.String(500), nullable=False)
    file = db.Column(db.String(200))  # Optional file attachment
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

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


@app.route('/admin/add_question', methods=['GET', 'POST'])
@login_required
def add_question():
    if not current_user.is_admin:
        return redirect(url_for('view_questions_by_department'))
    
    departments = Department.query.all()  # Fetch all departments
    
    if request.method == 'POST':
        question_text = request.form['question']
        department_id = request.form['department']  # Get selected department
        file = request.files.get('file')
        filename = secure_filename(file.filename) if file else None
        
        if filename:
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        new_question = Question(question=question_text, file=filename, department_id=department_id)
        db.session.add(new_question)
        db.session.commit()
        
        return redirect(url_for('admin_dashboard'))
    
    return render_template('add_question.html', departments=departments)
#view_reply_question_user to fetch questions and replies
@app.route('/view_reply_question_user', methods=['GET', 'POST'])
@login_required
def view_reply_question_user():
    # Fetch questions assigned to the user's department
    if current_user.department_id:
        questions = Question.query.filter_by(department_id=current_user.department_id).all()
    else:
        questions = []
    
    # Check if there are replies for each question
    for question in questions:
        question.replies = Reply.query.filter_by(question_id=question.id).all()

    return render_template('view_reply_question_user.html', questions=questions)

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

#view questions department wise 
@app.route('/questions', methods=['GET'])
@login_required
def view_questions_by_department():
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
        'view_questions_by_department.html',
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
        new_user = User(username=username, password=password, department_id=department_id, is_admin=is_admin)
        db.session.add(new_user)
        db.session.commit()
        flash('User added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('add_user.html', departments=departments)

# Route to view the list of users
@app.route('/admin/view_users', methods=['GET'])
@login_required
def view_users():
    if not current_user.is_admin:
        return redirect(url_for('department_dashboard'))
    
    users = User.query.all()  # Fetch all users
    return render_template('view_user.html', users=users)

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
            return redirect(url_for('add_department'))

        # Add new department
        new_department = Department(name=department_name)
        db.session.add(new_department)
        db.session.commit()
        flash('Department added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('add_department.html')

#view departments
@app.route('/admin/departments', methods=['GET'])
@login_required
def view_departments():
    if not current_user.is_admin:
        return redirect(url_for('department_dashboard'))
    
    departments = Department.query.all()  # Fetch all departments
    return render_template('view_departments.html', departments=departments)

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