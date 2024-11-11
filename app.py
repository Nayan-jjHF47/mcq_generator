
import os
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
import pdfplumber
import docx
import google.generativeai as genai
from fpdf import FPDF
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Set your API key
os.environ["GOOGLE_API_KEY"] = "AIzaSyDsZP7QuhrjMjUBtkLVaMAVUu70MaUbFGA"
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel("models/gemini-1.5-pro")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['RESULTS_FOLDER'] = 'results/'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt', 'docx'}
app.secret_key = 'Nayan@123'
# MySQL Database connection setup
db_config = {
    'user': 'root',
    'password': 'Nayan@123',
    'host': 'localhost',
    'database': 'mcq_generator_db'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)



def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_from_file(file_path):
    ext = file_path.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        with pdfplumber.open(file_path) as pdf:
            text = ''.join([page.extract_text() for page in pdf.pages])
        return text
    elif ext == 'docx':
        doc = docx.Document(file_path)
        text = ' '.join([para.text for para in doc.paragraphs])
        return text
    elif ext == 'txt':
        with open(file_path, 'r') as file:
            return file.read()
    return None

def Question_mcqs_generator(input_text, num_questions):
    prompt = f"""
    You are an AI assistant helping the user generate multiple-choice questions (MCQs) based on the following text:
    '{input_text}'
    Please generate {num_questions} MCQs from the text. Each question should have:
    - A clear question
    - Four answer options (labeled A, B, C, D)
    - The correct answer clearly indicated
    - An identified Bloom's taxonomy level (e.g., Remember, Understand, Apply, Analyze, Evaluate, Create) suitable for each question
    Format:
    ## MCQ
    Question: [question]
    A) [option A]
    B) [option B]
    C) [option C]
    D) [option D]
    Correct Answer: [correct option]
     Bloom's level: [Bloom's level]
    
    """
    response = model.generate_content(prompt).text.strip()
    return response


def save_mcqs_to_file(mcqs, filename):
    results_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    with open(results_path, 'w') as f:
        f.write(mcqs)
    return results_path

def create_pdf(mcqs, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for mcq in mcqs.split("## MCQ"):
        if mcq.strip():
            pdf.multi_cell(0, 10, mcq.strip())
            pdf.ln(5)  # Add a line break

    pdf_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
    pdf.output(pdf_path)
    return pdf_path

# Routes
@app.route('/')
def index():
    return render_template('index.html')


# Route for user signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                (username, email, password)
            )
            conn.commit()
            flash('Signup successful! Please log in.')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash('Username or email already taken.')
        finally:
            cursor.close()
            conn.close()
    return render_template('signup.html')


# Route for user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        # Check password hash
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('mcq'))

        flash('Invalid credentials.')

    return render_template('login.html')


# Route for user logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# Route for MCQ generation
@app.route('/mcq', methods=['GET', 'POST'])
def mcq():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file selected")
            return redirect(request.url)

        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            text = extract_text_from_file(file_path)

            if text:
                num_questions = int(request.form['num_questions'])
                mcqs = Question_mcqs_generator(text, num_questions)

                # File names for generated MCQ output
                txt_filename = f"generated_mcqs_{filename.rsplit('.', 1)[0]}.txt"
                pdf_filename = f"generated_mcqs_{filename.rsplit('.', 1)[0]}.pdf"

                # Save MCQs to text and PDF
                save_mcqs_to_file(mcqs, txt_filename)
                create_pdf(mcqs, pdf_filename)

                return render_template('results.html', mcqs=mcqs, txt_filename=txt_filename, pdf_filename=pdf_filename)

    return render_template('mcq.html')


# Route for downloading generated files
@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(app.config['RESULTS_FOLDER'], filename), as_attachment=True)


if __name__ == "__main__":
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    if not os.path.exists(app.config['RESULTS_FOLDER']):
        os.makedirs(app.config['RESULTS_FOLDER'])
    app.run(debug=True)




