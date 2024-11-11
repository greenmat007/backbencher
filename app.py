
from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = '12345'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site0.db'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    question_text = db.Column(db.String(500), nullable=False)
    option_a = db.Column(db.String(100), nullable=True)  # For single/multiple-choice questions
    option_b = db.Column(db.String(100), nullable=True)
    option_c = db.Column(db.String(100), nullable=True)
    option_d = db.Column(db.String(100), nullable=True)
    correct_option = db.Column(db.String(1), nullable=True)  # For single-choice questions
    correct_options = db.Column(db.String(100), nullable=True)  # Comma-separated correct answers for multiple-choice or fill-in-the-blank
    blanks = db.Column(db.Integer, nullable=True)  # Number of blanks for fill-in-the-blank questions
    question_type = db.Column(db.String(20), nullable=False, default="single")  # 'single', 'multiple', 'fill_in_the_blank'


class ExamAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    attempt_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='attempts', lazy=True)
    exam = db.relationship('Exam', backref='attempts', lazy=True)



# User Model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)



# Exam model (must be defined before Question model)
class Exam(db.Model):
    __tablename__ = 'exam'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    questions = db.relationship('Question', backref='exam', lazy=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and bcrypt.check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('user_home'))  # Redirect to user home page after login
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html')



@app.route("/exam1/<int:exam_id>/<int:question_number>", methods=['GET', 'POST'])
@login_required
def exam1(exam_id, question_number):
    # Fetch the exam and questions
    exam = Exam.query.get_or_404(exam_id)
    questions = Question.query.filter_by(exam_id=exam_id).all()

    # Check if question_number is within range
    if question_number < 1 or question_number > len(questions):
        return redirect(url_for('exam', exam_id=exam_id, question_number=1))

    # Get the current question based on the question_number
    question = questions[question_number - 1]

    # Handle the form submission for answering questions
    if request.method == 'POST':
        user_answer = request.form.get("answer")

        # Initialize score in session if it doesn't exist
        if 'score' not in session:
            session['score'] = 0
        
        
        print(question.correct_option)
        print(user_answer)
        # Update score if the answer is correct
        if user_answer == question.correct_option:
            session['score'] += 1
        session.modified = True  # Mark the session as modified to save changes

        # If it's the last question, save the score to the database
        if question_number == len(questions):
            final_score = session['score']
            
            # Save attempt to the database
            attempt = ExamAttempt(
                user_id=current_user.id,
                exam_id=exam_id,
                score=final_score,
                total_questions=len(questions),
                attempt_date=datetime.utcnow()
            )
            db.session.add(attempt)
            db.session.commit()

            # Clear score from session after the exam
            session.pop('score', None)
            return render_template('result.html', score=final_score, total=len(questions))

        # Redirect to the next question
        return redirect(url_for('exam', exam_id=exam_id, question_number=question_number + 1))

    # Render the current question page
    return render_template('exam_question.html', exam=exam, question=question, question_number=question_number, total_questions=len(questions))

@app.route("/exam/<int:exam_id>/<int:question_number>", methods=['GET', 'POST'])
@login_required
def exam(exam_id, question_number):
    exam = Exam.query.get_or_404(exam_id)
    questions = Question.query.filter_by(exam_id=exam_id).all()
    question = questions[question_number - 1]

    if request.method == 'POST':
        if question.question_type == 'fill_in_the_blank':
            # Handle fill-in-the-blank answers
            correct_answers = question.correct_options.split(',')
            user_correct_count = 0
            for i in range(1, question.blanks + 1):
                user_answer = request.form.get(f"blank{i}")
                if user_answer and user_answer.strip().lower() == correct_answers[i - 1].strip().lower():
                    user_correct_count += 1
            # Full score if all blanks are correct
            if user_correct_count == question.blanks:
                session['score'] = session.get('score', 0) + 1
        elif question.question_type == 'multiple':
            # Handle multiple-answer questions
            user_answers = request.form.getlist('answer')
            correct_answers = question.correct_options.split(',')
            if set(user_answers) == set(correct_answers):
                session['score'] = session.get('score', 0) + 1
        else:
            # Handle single-answer questions
            user_answer = request.form.get('answer')
            if user_answer == question.correct_option:
                session['score'] = session.get('score', 0) + 1
                

        print(session.get('score', 0))
            
        session.modified = True

        # If it's the last question, show the results
        if question_number == len(questions):
            final_score = session.get('score', 0)
            
            # Save attempt to the database
            attempt = ExamAttempt(
                user_id=current_user.id,
                exam_id=exam_id,
                score=final_score,
                total_questions=len(questions),
                attempt_date=datetime.utcnow()
            )
            db.session.add(attempt)
            db.session.commit()   
            
            session.pop('score', None)
            return render_template('result.html', score=final_score, total=len(questions))

        # Redirect to the next question
        return redirect(url_for('exam', exam_id=exam_id, question_number=question_number + 1))

    return render_template('exam_question.html', exam=exam, question=question, question_number=question_number, total_questions=len(questions))


@app.route("/check-answer", methods=['POST'])
@login_required
def check_answer():
    data = request.json
    exam_id = data.get('examId')
    question_number = int(data.get('questionNumber'))
    
    # Get the question
    questions = Question.query.filter_by(exam_id=exam_id).all()
    question = questions[question_number - 1]
    
    is_correct = False
    explanation = ""
    correct_answer = None
    
    if question.question_type == 'fill_in_the_blank':
        correct_answers = question.correct_options.split(',')
        user_answers = data.get('userAnswers', {})
        correct_count = 0
        
        for i in range(1, question.blanks + 1):
            user_answer = user_answers.get(f"blank{i}", "").strip().lower()
            if user_answer == correct_answers[i - 1].strip().lower():
                correct_count += 1
                
        is_correct = correct_count == question.blanks
        correct_answer = correct_answers
        explanation = f"The correct answer{'s are' if len(correct_answers) > 1 else ' is'}: {', '.join(correct_answers)}"
        
    elif question.question_type == 'multiple':
        user_answers = set(data.get('userAnswers', []))
        correct_answers = set(question.correct_options.split(','))
        is_correct = user_answers == correct_answers
        correct_answer = list(correct_answers)
        explanation = f"The correct answers are: {', '.join(correct_answer)}"
        
    else:  # single choice
        user_answer = data.get('userAnswers')
        is_correct = user_answer == question.correct_option
        correct_answer = question.correct_option
        explanation = f"The correct answer is: {question.correct_option}"
    
    return jsonify({
        'isCorrect': is_correct,
        'correctAnswer': correct_answer,
        'explanation': explanation
    })

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/user_home")
@login_required
def user_home():
    # Get all past attempts by the current user
    attempts = ExamAttempt.query.filter_by(user_id=current_user.id).order_by(ExamAttempt.attempt_date.desc()).all()
    exams = Exam.query.all()  # Fetch all available exams
    
    return render_template("user_home.html", exams=exams, attempts=attempts)


import google.generativeai as genai
from flask_cors import CORS

CORS(app)


# Configure the Gemini API
genai.configure(api_key='AIzaSyB265GIXXq5REPMHi_y_X1luKzaDFtgR6E')

# Initialize Gemini model
model = genai.GenerativeModel('gemini-pro')

@app.route('/ask-ai', methods=['POST'])
def ask_gemini():
    try:
        data = request.json
        question = data['messages'][0]['content']
        
        # Add better error handling and logging
        print(f"Received question: {question}")  # Debug log
        
        # Structure the prompt
        prompt = f"""Please help explain this exam question and provide guidance with respect to IGCSC sylabus. 
        Question: {question}
        Please provide:
        1. A clear explanation of the question
        2. Key concepts to consider
        3. Approach to solving it 
        """
        
        try:
            # Generate response using Gemini
            response = model.generate_content(prompt)
            
            # Debug logging
            print("API Response received")
            
            return jsonify({
                'response': response.text if hasattr(response, 'text') else str(response)
            })
            
        except Exception as api_error:
            print(f"Gemini API error: {str(api_error)}")  # Debug log
            return jsonify({
                'error': f"Gemini API error: {str(api_error)}"
            }), 500
    
    except Exception as e:
        print(f"Server error: {str(e)}")  # Debug log
        return jsonify({
            'error': f"Server error: {str(e)}"
        }), 500

@app.route('/check-with-ai', methods=['POST'])
def check_gemini():
    try:
        data = request.json
        exam_id = data['messages'][0]['examId']
        question_number = int(data['messages'][0]['questionNumber'])
        
        # Get the question
        questions = Question.query.filter_by(exam_id=exam_id).all()
        question = questions[question_number - 1]
        
        correct_answer = None
        correct_answers = question.correct_options       

        question_text = data['messages'][0]['content']
        
        # Add better error handling and logging
        print(f"Received question: {question}")  # Debug log
        
        # Structure the prompt
        prompt = f"""
        {question_text}
        expected answer: {correct_answers}
        Please provide:
        1. A clear explanation why the useranswer: is correct or incorrect or partialy correct with a score from 0 to 100 based on the  expected answer
        """
        
        try:
            # Generate response using Gemini
            response = model.generate_content(prompt)
            
            # Debug logging
            print("API Response received")
            
            return jsonify({
                'response': response.text if hasattr(response, 'text') else str(response)
            })
            
        except Exception as api_error:
            print(f"Gemini API error: {str(api_error)}")  # Debug log
            return jsonify({
                'error': f"Gemini API error: {str(api_error)}"
            }), 500
    
    except Exception as e:
        print(f"Server error: {str(e)}")  # Debug log
        return jsonify({
            'error': f"Server error: {str(e)}"
        }), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Creates database tables if they don't exist
    app.run(host='0.0.0.0', port=80, debug=True)
