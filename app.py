import os
import sqlite3
import secrets
import smtplib
from email.mime.text import MIMEText
from functools import wraps
from flask import Flask, render_template, request, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'super_secret_secure_voting_key_change_in_production'
DATABASE = 'voting.db'

EMAIL_ADDRESS = "securevote4@gmail.com"
EMAIL_PASSWORD = "gxlbqpupbvrgykpd"

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DATABASE):
        with app.app_context():
            conn = get_db_connection()
            with app.open_resource('schema.sql', mode='r') as f:
                conn.cursor().executescript(f.read())
            
            admin_pwd = generate_password_hash('admin123')
            conn.execute('INSERT INTO main_admins (username, password_hash) VALUES (?, ?)', ('admin', admin_pwd))
            conn.execute('INSERT INTO election_status (id, is_active) VALUES (1, 0)')
            
            conn.commit()
            conn.close()
            print("Database initialized with default admin (admin / admin123).")

init_db()

@app.route('/')
def index():
    return render_template('index.html')
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please log in as Admin to access this page.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def dept_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('dept_logged_in'):
            flash('Please log in as Department Tutor to access this page.', 'error')
            return redirect(url_for('dept_login'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('student_logged_in'):
            flash('Please enter a valid voting token.', 'error')
            return redirect(url_for('vote_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Admin Routes ---
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        admin = conn.execute('SELECT * FROM main_admins WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if admin and check_password_hash(admin['password_hash'], password):
            session['admin_logged_in'] = True
            flash('Logged in successfully.', 'success')
            return redirect(url_for('admin_dashboard'))
        flash('Invalid username or password.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logged out successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    status = conn.execute('SELECT is_active FROM election_status WHERE id = 1').fetchone()
    is_active = bool(status['is_active']) if status else False
    
    departments = conn.execute('SELECT id, dept_code, dept_name FROM departments').fetchall()
    
    # Calculate results
    results = conn.execute('''
        SELECT c.id, c.name, c.gender, d.dept_name, 
               (SELECT COUNT(*) FROM votes WHERE boy_candidate_id = c.id OR girl_candidate_id = c.id) as votes
        FROM candidates c
        JOIN departments d ON c.department_id = d.id
        ORDER BY votes DESC
    ''').fetchall()
    
    winners = {'boy': None, 'girl': None}
    if not is_active:
        boys = [r for r in results if r['gender'] == 'Boy']
        girls = [r for r in results if r['gender'] == 'Girl']
        if boys: winners['boy'] = max(boys, key=lambda x: x['votes'])
        if girls: winners['girl'] = max(girls, key=lambda x: x['votes'])
        
    conn.close()
    return render_template('admin_dashboard.html', 
                           is_active=is_active, 
                           departments=departments, 
                           results=results, 
                           winners=winners)

@app.route('/admin/create_dept', methods=['POST'])
@admin_required
def create_dept():
    dept_name = request.form['dept_name']
    dept_code = request.form['dept_code']
    password = request.form['password']
    
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO departments (dept_code, dept_name, password_hash) VALUES (?, ?, ?)',
                     (dept_code, dept_name, generate_password_hash(password)))
        conn.commit()
        flash(f'Department {dept_name} created successfully.', 'success')
    except sqlite3.IntegrityError:
        flash('Department code already exists.', 'error')
    finally:
        conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle_election', methods=['POST'])
@admin_required
def toggle_election():
    conn = get_db_connection()
    status = conn.execute('SELECT is_active FROM election_status WHERE id = 1').fetchone()
    new_status = 0 if status and status['is_active'] else 1
    
    conn.execute('UPDATE election_status SET is_active = ? WHERE id = 1', (new_status,))
    conn.commit()
    conn.close()
    
    state_str = "started" if new_status else "ended"
    flash(f'Election has been {state_str}.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/dept', methods=['GET', 'POST'])
def dept_login():
    if request.method == 'POST':
        dept_code = request.form['dept_code']
        password = request.form['password']
        
        conn = get_db_connection()
        dept = conn.execute('SELECT * FROM departments WHERE dept_code = ?', (dept_code,)).fetchone()
        conn.close()
        
        if dept and check_password_hash(dept['password_hash'], password):
            session['dept_logged_in'] = True
            session['dept_id'] = dept['id']
            session['dept_name'] = dept['dept_name']
            flash(f'Logged in to {dept["dept_name"]} successfully.', 'success')
            return redirect(url_for('dept_dashboard'))
        flash('Invalid department code or password.', 'error')
    return render_template('dept_login.html')

@app.route('/dept/logout')
def dept_logout():
    session.pop('dept_logged_in', None)
    session.pop('dept_id', None)
    session.pop('dept_name', None)
    flash('Logged out from department successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/dept/dashboard')
@dept_required
def dept_dashboard():
    dept_id = session['dept_id']
    conn = get_db_connection()
    status = conn.execute('SELECT is_active FROM election_status WHERE id = 1').fetchone()
    is_active = bool(status['is_active']) if status else False
    
    students_count = conn.execute('SELECT COUNT(*) FROM students WHERE department_id = ?', (dept_id,)).fetchone()[0]
    tokens_count = conn.execute('SELECT COUNT(*) FROM tokens WHERE department_id = ?', (dept_id,)).fetchone()[0]
    
    results = conn.execute('''
        SELECT c.id, c.name, c.gender, 
               (SELECT COUNT(*) FROM votes WHERE (boy_candidate_id = c.id OR girl_candidate_id = c.id) 
                AND department_id = ?) as votes
        FROM candidates c
        WHERE c.department_id = ?
        ORDER BY votes DESC
    ''', (dept_id, dept_id)).fetchall()
    conn.close()
    
    stats = {'students': students_count, 'tokens': tokens_count}
    return render_template('dept_dashboard.html', 
                           dept_name=session['dept_name'],
                           is_active=is_active, 
                           stats=stats, 
                           results=results)

@app.route('/dept/register_student', methods=['POST'])
@dept_required
def register_student():
    student_name = request.form['student_name']
    student_email = request.form['student_email']
    dept_id = session['dept_id']
    
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO students (department_id, name, email) VALUES (?, ?, ?)',
                     (dept_id, student_name, student_email))
        conn.commit()
        flash(f'Student {student_name} registered successfully.', 'success')
    except sqlite3.IntegrityError:
        flash('Student email already exists.', 'error')
    finally:
        conn.close()
    return redirect(url_for('dept_dashboard'))

@app.route('/dept/register_candidate', methods=['POST'])
@dept_required
def register_candidate():
    candidate_name = request.form['candidate_name']
    gender = request.form['gender']
    dept_id = session['dept_id']
    
    conn = get_db_connection()
    conn.execute('INSERT INTO candidates (department_id, name, gender) VALUES (?, ?, ?)',
                 (dept_id, candidate_name, gender))
    conn.commit()
    conn.close()
    flash(f'Candidate {candidate_name} ({gender}) registered successfully.', 'success')
    return redirect(url_for('dept_dashboard'))

@app.route('/dept/generate_tokens', methods=['POST'])
@dept_required
def generate_tokens():
    dept_id = session['dept_id']
    conn = get_db_connection()

    status = conn.execute(
        'SELECT is_active FROM election_status WHERE id = 1'
    ).fetchone()

    if status and status['is_active']:
        flash('Cannot generate tokens while election is active.', 'error')
        conn.close()
        return redirect(url_for('dept_dashboard'))

    students = conn.execute(
        'SELECT id, name, email FROM students WHERE department_id = ?',
        (dept_id,)
    ).fetchall()

    new_tokens = 0

    for student in students:
        existing = conn.execute(
            'SELECT id FROM tokens WHERE student_id = ?',
            (student['id'],)
        ).fetchone()

        if not existing:
            token = secrets.token_urlsafe(8)

            conn.execute(
                'INSERT INTO tokens (student_id, department_id, token_value) VALUES (?, ?, ?)',
                (student['id'], dept_id, token)
            )
            try:
                msg = MIMEText(
                    f"Hello {student['name']},\n\n"
                    f"Your secure voting token is:\n\n{token}\n\n"
                    "Use this token to vote in the election."
                )

                msg['Subject'] = "Your Secure Voting Token"
                msg['From'] = EMAIL_ADDRESS
                msg['To'] = student['email']

                server = smtplib.SMTP("smtp.gmail.com", 587)
                server.starttls()
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

                server.sendmail(
                    EMAIL_ADDRESS,
                    student['email'],
                    msg.as_string()
                )

                server.quit()

            except Exception as e:
                print("Email sending failed:", e)

            new_tokens += 1

    conn.commit()
    conn.close()

    if new_tokens > 0:
        flash(f'Successfully generated and emailed {new_tokens} new tokens.', 'success')
    else:
        flash('All registered students already have tokens.', 'success')

    return redirect(url_for('dept_dashboard'))

# --- Student Voting Routes ---
@app.route('/vote/login', methods=['GET', 'POST'])
def vote_login():
    if request.method == 'POST':
        token_value = request.form['token'].strip()
        
        conn = get_db_connection()
        status = conn.execute('SELECT is_active FROM election_status WHERE id = 1').fetchone()
        if not status or not status['is_active']:
            flash('There is currently no active election.', 'error')
            conn.close()
            return redirect(url_for('vote_login'))
        
        token_rec = conn.execute('''
            SELECT t.id, t.is_used, t.student_id, t.department_id, s.name as student_name, d.dept_name
            FROM tokens t
            JOIN students s ON t.student_id = s.id
            JOIN departments d ON t.department_id = d.id
            WHERE t.token_value = ?
        ''', (token_value,)).fetchone()
        conn.close()
        
        if token_rec:
            if token_rec['is_used']:
                flash('This token has already been used to vote.', 'error')
            else:
                session['student_logged_in'] = True
                session['student_id'] = token_rec['student_id']
                session['student_name'] = token_rec['student_name']
                session['department_id'] = token_rec['department_id']
                session['dept_name'] = token_rec['dept_name']
                session['token_id'] = token_rec['id']
                return redirect(url_for('vote'))
        else:
            flash('Invalid token entered.', 'error')
            
    return render_template('vote_login.html')

@app.route('/vote')
@student_required
def vote():
    dept_id = session['department_id']
    conn = get_db_connection()
    status = conn.execute('SELECT is_active FROM election_status WHERE id = 1').fetchone()
    if not status or not status['is_active']:
        flash('The election has ended. You can no longer vote.', 'error')
        conn.close()
        return redirect(url_for('vote_logout'))
    token_used = conn.execute('SELECT is_used FROM tokens WHERE id = ?', (session['token_id'],)).fetchone()[0]
    if token_used:
        flash('This token was already used.', 'error')
        conn.close()
        return redirect(url_for('vote_logout'))

    boys = conn.execute('SELECT id, name FROM candidates WHERE department_id = ? AND gender = "Boy"', (dept_id,)).fetchall()
    girls = conn.execute('SELECT id, name FROM candidates WHERE department_id = ? AND gender = "Girl"', (dept_id,)).fetchall()
    conn.close()
    
    return render_template('vote.html', 
                           student_name=session['student_name'], 
                           dept_name=session['dept_name'],
                           boys=boys, girls=girls)

@app.route('/vote/submit', methods=['POST'])
@student_required
def submit_vote():
    boy_id = request.form.get('boy_candidate_id')
    girl_id = request.form.get('girl_candidate_id')
    
    if not boy_id or not girl_id:
        flash('You must select exactly one boy and one girl candidate.', 'error')
        return redirect(url_for('vote'))
        
    dept_id = session['department_id']
    token_id = session['token_id']
    
    conn = get_db_connection()
    
    status = conn.execute('SELECT is_active FROM election_status WHERE id = 1').fetchone()
    if not status or not status['is_active']:
        flash('The election has ended.', 'error')
        conn.close()
        return redirect(url_for('vote_logout'))
        
    try:
        is_used = conn.execute('SELECT is_used FROM tokens WHERE id = ?', (token_id,)).fetchone()[0]
        if is_used:
            flash('Your vote has already been recorded successfully.', 'error')
            conn.close()
            return redirect(url_for('vote_logout'))

        conn.execute('''
            INSERT INTO votes (department_id, boy_candidate_id, girl_candidate_id)
            VALUES (?, ?, ?)
        ''', (dept_id, boy_id, girl_id))
        
        conn.execute('UPDATE tokens SET is_used = 1 WHERE id = ?', (token_id,))
        
        conn.commit()
        flash('Your official ballot has been cast successfully! Thank you for voting.', 'success')
        
    except Exception as e:
        conn.rollback()
        flash('An error occurred submitting your vote.', 'error')
    finally:
        conn.close()
        
    return redirect(url_for('vote_logout'))

@app.route('/vote/logout')
def vote_logout():
    session.pop('student_logged_in', None)
    session.pop('student_id', None)
    session.pop('student_name', None)
    session.pop('department_id', None)
    session.pop('dept_name', None)
    session.pop('token_id', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)



#admin password admin123
#admin can create password for other department  techers
 