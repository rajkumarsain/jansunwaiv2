from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads/'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Ensure the uploads directory exists
if not os.path.exists('uploads'):
    os.makedirs('uploads')

# Create User model
# User model with SQLAlchemy
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # Check if the user is an admin

# Question model
class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False)
    file = db.Column(db.String(200))  # Optional file attachment

# Reply model
class Reply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reply = db.Column(db.String(500), nullable=False)
    file = db.Column(db.String(200))  # Optional file attachment
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

def create_default_users():
    # Check if users already exist
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', password='admin123', is_admin=True)
        db.session.add(admin_user)

    if not User.query.filter_by(username='client').first():
        client_user = User(username='client', password='client123', is_admin=False)
        db.session.add(client_user)

    db.session.commit()

# Function to load user based on user_id
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    return render_template('base.html')

# login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        # Check if the user exists and the password matches
        if user and user.password == password:
            login_user(user)  # Log the user in

            # Redirect based on user role
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
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
        return redirect(url_for('user_dashboard'))
    questions = Question.query.all()
    return render_template('admin_dashboard.html', questions=questions)

@app.route('/admin/add_question', methods=['GET', 'POST'])
@login_required
def add_question():
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
    
    if request.method == 'POST':
        question_text = request.form['question']
        file = request.files.get('file')
        filename = secure_filename(file.filename) if file else None
        if filename:
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        new_question = Question(question=question_text, file=filename)
        db.session.add(new_question)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    
    return render_template('add_question.html')

# User routes
@app.route('/user/dashboard')
@login_required
def user_dashboard():
    questions = Question.query.all()
    return render_template('user_dashboard.html', questions=questions)
 
@app.route('/question/<int:question_id>', methods=['GET', 'POST'])
@login_required
def view_question(question_id):
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
        return redirect(url_for('view_question', question_id=question_id))
    
    return render_template('view_question.html', question=question, replies=replies)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_default_users()  # Populate the database with default admin and client users
    app.run(debug=True)