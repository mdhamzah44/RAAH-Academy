from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for, session, request
from flask_mysqldb import MySQL
from flask_socketio import SocketIO, emit, join_room, leave_room
import logging
import os
import json
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import pdfkit

app = Flask(__name__)

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'canvas_app'

# Initialize MySQL
mysql = MySQL(app)

# Secret key for session
app.secret_key = 'your_secure_random_string_here'
user_responses = {}

# Directory for storing canvas data
DATA_DIR = 'data'
os.makedirs(DATA_DIR, exist_ok=True)

# Configure pdfkit
if os.name == 'nt':  # For Windows
    path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
else:  # For Linux/Mac
    path_wkhtmltopdf = '/usr/local/bin/wkhtmltopdf'  # Adjust this path if necessary

config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

# Initialize SocketIO
socketio = SocketIO(app)

@app.route('/')
def home():
    if 'user_id' in session:
        if session['role'] == 'teacher':
            return redirect(url_for('teacher_home'))
        elif session['role'] == 'student':
            return redirect(url_for('student_home'))
    return redirect(url_for('login'))

@app.route('/create_class', methods=['POST'])
def create_class():
    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    subject = request.form['subject']
    date = request.form['date']
    time = request.form['time']

    cur = mysql.connection.cursor()
    try:
        cur.execute("INSERT INTO classes (teacher_id, subject, date, time) VALUES (%s, %s, %s, %s)",
                    (session['user_id'], subject, date, time))
        mysql.connection.commit()
        
        # Get the ID of the newly created class
        class_id = cur.lastrowid
        
        # Create a new JSON file for the class
        json_filename = f'class_{class_id}_data.json'
        json_filepath = os.path.join(DATA_DIR, json_filename)
        
        # Initialize the JSON file with an empty structure
        initial_data = {
            "slides": [],
            "currentSlideIndex": 0
        }
        
        with open(json_filepath, 'w') as json_file:
            json.dump(initial_data, json_file)
        
        return redirect(url_for('teacher_home'))
    except Exception as e:
        # Handle any exceptions (e.g., database errors)
        print(f"Error creating class: {e}")
        mysql.connection.rollback()
        return "Error creating class", 500
    finally:
        cur.close()

@app.route('/teacher_home')
def teacher_home():
    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))
    
    # Fetch classes for the teacher along with the number of enrolled students
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT c.id, c.subject, c.date, c.time, c.status, COUNT(uc.user_id) as enrolled_count
        FROM classes c
        LEFT JOIN user_classes uc ON c.id = uc.class_id
        WHERE c.teacher_id = %s
        GROUP BY c.id
        ORDER BY c.date, c.time
    """, (session['user_id'],))
    classes = []
    for row in cur.fetchall():
        classes.append({
            'id': row[0],
            'subject': row[1],
            'date': row[2].strftime('%Y-%m-%d'),
            'time': row[3].strftime('%H:%M') if isinstance(row[3], datetime) else row[3],
            'status': row[4],
            'enrolled_count': row[5]
        })
    cur.close()

    return render_template('teacher_home.html', username=session['username'], classes=classes)

@app.route('/student_home')
def student_home():
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('login'))
    
    # Fetch upcoming classes for the student
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT c.id, c.subject, u.username, c.date, c.time, c.status
        FROM classes c
        JOIN users u ON c.teacher_id = u.id
        WHERE c.date >= CURDATE()
        ORDER BY c.date, c.time
    """)
    classes = []
    for row in cur.fetchall():
        classes.append({
            'id': row[0],
            'subject': row[1],
            'teacher': row[2],
            'date': row[3].strftime('%Y-%m-%d'),
            'time': row[4].strftime('%H:%M') if isinstance(row[4], datetime) else row[4],
            'status': row[5],
            'client_url': url_for('client', class_id=row[0])
        })
    cur.close()

    # Fetch enrolled classes for the student
    cur = mysql.connection.cursor()
    cur.execute("SELECT class_id FROM user_classes WHERE user_id = %s", (session['user_id'],))
    enrolled_classes = [row[0] for row in cur.fetchall()]
    cur.close()

    return render_template('student_home.html', username=session['username'], classes=classes, enrolled_classes=enrolled_classes)


@app.route('/enroll_class/<int:class_id>', methods=['POST'])
def enroll_class(class_id):
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO user_classes (user_id, class_id) VALUES (%s, %s)", (session['user_id'], class_id))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('student_home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        
        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[4]
            return redirect(url_for('home'))
        
        return render_template('login.html', error="Invalid credentials")
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        
        hashed_password = generate_password_hash(password)
        
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
                    (username, email, hashed_password, role))
        mysql.connection.commit()
        cur.close()
        
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))

@app.route('/index/<int:class_id>')
def index(class_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))
    
    json_filename = f'class_{class_id}_data.json'
    json_filepath = os.path.join(DATA_DIR, json_filename)
    
    # Check if the file exists, if not, create it with initial data
    if not os.path.exists(json_filepath):
        initial_data = {
            "slides": [],
            "currentSlideIndex": 0
        }
        with open(json_filepath, 'w') as json_file:
            json.dump(initial_data, json_file)
    
    return render_template('index.html', class_id=class_id)

@app.route('/get_canvas_data/<int:class_id>')
def get_canvas_data(class_id):
    if 'user_id' not in session:
        app.logger.error(f"Unauthorized access attempt for class {class_id}")
        return jsonify({'error': 'Unauthorized'}), 401

    json_filename = f'class_{class_id}_data.json'
    json_filepath = os.path.join(DATA_DIR, json_filename)
    
    try:
        with open(json_filepath, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        app.logger.error(f"Canvas data file not found for class {class_id}")
        return jsonify({'slides': [], 'currentSlideIndex': 0})
    except Exception as e:
        app.logger.error(f"Error loading canvas data for class {class_id}: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500

@app.route('/update', methods=['POST'])
def update_canvas():
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    class_id = data.get('class_id')
    if class_id is None:
        return jsonify({'error': 'Missing class_id'}), 400

    json_filename = f'class_{class_id}_data.json'
    json_filepath = os.path.join(DATA_DIR, json_filename)
    
    with open(json_filepath, 'w') as f:
        json.dump(data, f)
    return jsonify({'status': 'success'})

@app.route('/fetch')
def fetch_canvas():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        with open(os.path.join(DATA_DIR, 'canvas_data.json'), 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({'slides': [], 'currentSlideIndex': 0})

@app.route('/add_comment', methods=['POST'])
def add_comment():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    comment = request.json.get('comment')
    class_id = request.json.get('class_id')
    if comment and class_id:
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO comments (user_id, username, comment, created_at, class_id) VALUES (%s, %s, %s, %s, %s)",
                    (session['user_id'], session['username'], comment, datetime.now(), class_id))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'No comment or class_id provided'}), 400



@app.route('/end_class/<int:class_id>', methods=['POST'])
def end_class(class_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        # Get the canvas data
        json_filename = f'class_{class_id}_data.json'
        json_filepath = os.path.join(DATA_DIR, json_filename)
        with open(json_filepath, 'r') as f:
            canvas_data = json.load(f)

        # Generate HTML for PDF
        html_content = "<html><body>"
        for slide in canvas_data['slides']:
            html_content += f"<img src='{slide['data']}' style='width: 100%; page-break-after: always;'>"
        html_content += "</body></html>"

        # Generate PDF
        pdf_path = os.path.join(DATA_DIR, f'class_{class_id}_slides.pdf')
        pdfkit.from_string(html_content, pdf_path, configuration=config)

        # Update class status in database
        cur = mysql.connection.cursor()
        cur.execute("UPDATE classes SET status = 'ended' WHERE id = %s", (class_id,))
        mysql.connection.commit()
        cur.close()

        return jsonify({'status': 'success', 'message': 'Class ended and slides exported to PDF'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/check_class_status/<int:class_id>')
def check_class_status(class_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT status FROM classes WHERE id = %s", (class_id,))
    result = cur.fetchone()
    cur.close()

    if result:
        return jsonify({'status': result[0]})
    else:
        return jsonify({'status': 'not_found'}), 404

@app.route('/client/<int:class_id>')
def client(class_id):
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('login'))
    
    # Fetch the class details
    cur = mysql.connection.cursor()
    cur.execute("SELECT subject FROM classes WHERE id = %s", (class_id,))
    class_details = cur.fetchone()
    cur.close()
    
    if not class_details:
        return "Class not found", 404
    
    return render_template('client.html', class_id=class_id, subject=class_details[0])

@socketio.on('video_frame')
def handle_video_frame(data):
    class_id = data['class_id']
    frame = data['frame']
    emit('video_frame', {'frame': frame}, room=f'class_{class_id}', include_self=False)

@socketio.on('audio')
def handle_audio(data):
    class_id = data['class_id']
    audio = data['audio']
    emit('audio', {'audio': audio}, room=f'class_{class_id}', include_self=False)

@socketio.on('join')
def on_join(data):
    class_id = data['class_id']
    join_room(f'class_{class_id}')

@socketio.on('offer')
def handle_offer(data):
    class_id = data['class_id']
    offer = data['offer']
    emit('offer', {'offer': offer}, room=f'class_{class_id}', include_self=False)

@socketio.on('answer')
def handle_answer(data):
    class_id = data['class_id']
    answer = data['answer']
    emit('answer', {'answer': answer}, room=f'class_{class_id}', include_self=False)

@socketio.on('ice_candidate')
def handle_ice_candidate(data):
    class_id = data['class_id']
    candidate = data['candidate']
    print(f"Received ICE candidate for class_{class_id}")
    emit('ice_candidate', {'candidate': candidate}, room=f'class_{class_id}', include_self=False)

@socketio.on('request_offer')
def handle_request_offer(data):
    class_id = data['class_id']
    print(f"Received request for offer in class_{class_id}")
    emit('request_offer', {}, room=f'class_{class_id}', include_self=False)

@socketio.on('start_poll')
def handle_start_poll(data):
    class_id = data['class_id']
    start_time = datetime.now()
    end_time = start_time + timedelta(seconds=data['duration'])
    
    poll_data = {
        'pollId': data['pollId'],
        'question': data['question'],
        'options': data['options'],
        'correctAnswer': data['correctAnswer'],
        'startTime': start_time.isoformat(),
        'endTime': end_time.isoformat()
    }
    
    filename = f"poll_{class_id}.json"
    with open(filename, 'w') as f:
        json.dump(poll_data, f)
    
    print(f"Created poll file: {filename}")
    socketio.emit('poll_file_created', {'filename': filename}, room=class_id)


@app.route('/get_poll/<int:class_id>')
def get_poll(class_id):
    filename = f"poll_{class_id}.json"
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            poll_data = json.load(f)
        return jsonify(poll_data)
    else:
        return jsonify({'error': 'No active poll'}), 404

@socketio.on('submit_answer')
def handle_submit_answer(data):
    poll_id = data['pollId']
    user_id = request.sid  # Use Socket.IO session ID as user ID

    if poll_id not in user_responses:
        user_responses[poll_id] = {}

    if user_id in user_responses[poll_id]:
        return {'status': 'error', 'message': 'You have already answered this poll'}

    user_responses[poll_id][user_id] = {
        'answer': data['answer'],
        'correct': data['answer'] == data['correctAnswer']
    }

    cur = mysql.connection.cursor()
    try:
        query = """
        INSERT INTO poll_responses 
        (poll_id, class_id, user_id, answer, correct_answer, timestamp) 
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        values = (
            poll_id,
            data['classId'],
            user_id,
            data['answer'],
            data['correctAnswer'],
            datetime.now()
        )
        cur.execute(query, values)
        mysql.connection.commit()
        print("Answer stored in database")
        return {'status': 'success', 'message': 'Answer submitted successfully'}
    except Exception as e:
        print(f"Error inserting poll response: {e}")
        mysql.connection.rollback()
        return {'status': 'error', 'message': 'Failed to submit answer'}
    finally:
        cur.close()

@socketio.on('get_poll_results')
def handle_get_poll_results(data):
    poll_id = data['pollId']
    class_id = data['classId']

    cur = mysql.connection.cursor()
    try:
        query = """
        SELECT u.username, pr.answer, pr.correct_answer
        FROM poll_responses pr
        JOIN users u ON pr.user_id = u.id
        WHERE pr.poll_id = %s AND pr.class_id = %s
        """
        cur.execute(query, (poll_id, class_id))
        results = cur.fetchall()

        correct_answers = []
        incorrect_answers = []

        for username, answer, correct_answer in results:
            if answer == correct_answer:
                correct_answers.append(username)
            else:
                incorrect_answers.append(username)

        emit('poll_results', {
            'correctAnswers': correct_answers,
            'incorrectAnswers': incorrect_answers
        })

    except Exception as e:
        print(f"Error fetching poll results: {e}")
        emit('poll_results', {'error': 'Failed to fetch poll results'})
    finally:
        cur.close()


@app.route('/fetch_comments/<int:class_id>')
def fetch_comments(class_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    cur = mysql.connection.cursor()
    
    # Fetch the pinned comment
    cur.execute("SELECT id, username, comment, created_at FROM comments WHERE class_id = %s AND pinned = TRUE LIMIT 1", (class_id,))
    pinned_comment = cur.fetchone()
    
    # Fetch regular comments
    cur.execute("SELECT id, username, comment, created_at FROM comments WHERE class_id = %s AND pinned = FALSE ORDER BY created_at DESC LIMIT 50", (class_id,))
    comments = cur.fetchall()
    
    cur.close()

    result = {
        'pinnedComment': {
            'id': pinned_comment[0],
            'username': pinned_comment[1],
            'comment': pinned_comment[2],
            'created_at': pinned_comment[3].strftime('%Y-%m-%d %H:%M:%S')
        } if pinned_comment else None,
        'comments': [{
            'id': comment[0],
            'username': comment[1],
            'comment': comment[2],
            'created_at': comment[3].strftime('%Y-%m-%d %H:%M:%S')
        } for comment in comments]
    }

    return jsonify(result)

@app.route('/pin_comment', methods=['POST'])
def pin_comment():
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    comment_id = data['comment_id']
    class_id = data['class_id']

    cur = mysql.connection.cursor()
    try:
        # Unpin any previously pinned comment for this class
        cur.execute("UPDATE comments SET pinned = FALSE WHERE class_id = %s AND pinned = TRUE", (class_id,))
        # Pin the selected comment
        cur.execute("UPDATE comments SET pinned = TRUE WHERE id = %s AND class_id = %s", (comment_id, class_id))
        mysql.connection.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error pinning comment: {e}")
        mysql.connection.rollback()
        return jsonify({'status': 'error', 'message': 'Failed to pin comment'}), 500
    finally:
        cur.close()

@app.route('/unpin_comment', methods=['POST'])
def unpin_comment():
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    comment_id = data['comment_id']
    class_id = data['class_id']

    cur = mysql.connection.cursor()
    try:
        cur.execute("UPDATE comments SET pinned = FALSE WHERE id = %s AND class_id = %s", (comment_id, class_id))
        mysql.connection.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error unpinning comment: {e}")
        mysql.connection.rollback()
        return jsonify({'status': 'error', 'message': 'Failed to unpin comment'}), 500
    finally:
        cur.close()

@socketio.on('update_slide')
def handle_slide_update(data):
    room = f"class_{data['class_id']}"
    emit('slide_updated', data, room=room, include_self=False)

@app.errorhandler(404)
def page_not_found(e):
    app.logger.error(f'Page not found: {request.url}')
    return render_template('404.html'), 404


if __name__ == '__main__':
    socketio.run(app, debug=True)
