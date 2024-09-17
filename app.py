from flask import Flask, render_template, Response, request, redirect, url_for, session
import cv2
import logging
import sqlite3
import hashlib
import os
import datetime
import database

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Generate a secure random secret key

# Initialize the database
database.init_app(app)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Helper functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_password(stored_password, provided_password):
    return stored_password == hash_password(provided_password)

def get_user(username):
    db = database.get_db()
    user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    return user

def add_user(username, password, role='user'):
    db = database.get_db()
    
    # Check if any users exist
    user_count = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    
    # Automatically set the first user as admin
    if user_count == 0:
        role = 'admin'
    
    db.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
               (username, hash_password(password), role))
    db.commit()

def update_password(username, new_password):
    db = database.get_db()
    db.execute('UPDATE users SET password = ? WHERE username = ?',
               (hash_password(new_password), username))
    db.commit()

def add_camera(ip, port, path, username=None, password=None, location=None):
    db = database.get_db()
    db.execute('INSERT INTO cameras (ip, port, path, username, password, location) VALUES (?, ?, ?, ?, ?, ?)',
               (ip, port, path, username, password, location))
    db.commit()

def update_camera(camera_id, ip, port, path, username=None, password=None, location=None):
    db = database.get_db()
    db.execute('UPDATE cameras SET ip = ?, port = ?, path = ?, username = ?, password = ?, location = ? WHERE id = ?',
               (ip, port, path, username, password, location, camera_id))
    db.commit()

def get_cameras():
    db = database.get_db()
    return db.execute('SELECT * FROM cameras').fetchall()

def validate_rtsp(camera_url):
    cap = cv2.VideoCapture(camera_url)
    if not cap.isOpened():
        logging.error(f"Failed to open RTSP stream: {camera_url}")
        return False
    success, _ = cap.read()
    cap.release()
    return success

def check_admin_exists():
    db = database.get_db()
    cursor = db.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    return cursor.fetchone()[0] > 0

def log_login(username):
    db = database.get_db()
    now = datetime.datetime.now()
    db.execute('UPDATE users SET last_login = ? WHERE username = ?', (now, username))
    db.commit()

@app.route('/initialize_admin', methods=['GET', 'POST'])
def initialize_admin():
    if check_admin_exists():
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username and password:
            try:
                add_user(username, password)
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                return 'Username already exists', 400
        return 'Username and password required', 400
    
    return render_template('initialize_admin.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = get_user(username)
        if user and check_password(user['password'], password):
            session['logged_in'] = True
            session['username'] = username
            log_login(username)  # Log the login timestamp
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid credentials')
    
    if 'logged_in' not in session and not check_admin_exists():
        return redirect(url_for('initialize_admin'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    cameras = get_cameras()
    db = database.get_db()
    users = db.execute('SELECT username, last_login FROM users').fetchall()
    return render_template('index.html', cameras=cameras, users=users)

def gen_frames(camera_url):
    cap = cv2.VideoCapture(camera_url)
    
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()

def capture_snapshot(camera_url):
    cap = cv2.VideoCapture(camera_url)
    if not cap.isOpened():
        logging.error(f"Failed to open RTSP stream: {camera_url}")
        return None
    
    success, frame = cap.read()
    cap.release()
    
    if success:
        ret, buffer = cv2.imencode('.jpg', frame)
        return buffer.tobytes()
    else:
        logging.error(f"Failed to capture snapshot from RTSP stream: {camera_url}")
        return None

@app.route('/snapshot/<int:camera_id>')
def snapshot(camera_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    cameras = get_cameras()
    if camera_id < len(cameras):
        camera = cameras[camera_id]
        camera_url = f'rtsp://{camera["username"]}:{camera["password"]}@{camera["ip"]}:{camera["port"]}/{camera["path"]}'
        image_data = capture_snapshot(camera_url)
        if image_data:
            return Response(image_data, mimetype='image/jpeg')
        else:
            return "Failed to capture snapshot", 500
    else:
        return "Camera not found", 404

@app.route('/video_feed/<int:camera_id>')
def video_feed(camera_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    cameras = get_cameras()
    if camera_id < len(cameras):
        camera = cameras[camera_id]
        camera_url = f'rtsp://{camera["username"]}:{camera["password"]}@{camera["ip"]}:{camera["port"]}/{camera["path"]}'
        return Response(gen_frames(camera_url), mimetype='multipart/x-mixed-replace; boundary=frame')
    else:
        return "Camera not found", 404

@app.route('/add_camera', methods=['POST'])
def add_camera_route():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    ip = request.form['camera_ip']
    port = int(request.form['camera_port'])
    path = request.form['camera_path']
    username = request.form.get('camera_username')
    password = request.form.get('camera_password')
    location = request.form.get('camera_location')

    if username and password:
        camera_url = f'rtsp://{username}:{password}@{ip}:{port}/{path}'
    else:
        camera_url = f'rtsp://{ip}:{port}/{path}'

    if validate_rtsp(camera_url):
        add_camera(ip, port, path, username, password, location)
        logging.debug(f"RTSP camera added successfully with URL: {camera_url}")
    else:
        logging.error("Invalid RTSP camera URL or stream error")
        return 'Invalid RTSP camera URL or stream error', 400

    return redirect(url_for('index'))

@app.route('/update_camera/<int:camera_id>', methods=['POST'])
def update_camera(camera_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    ip = request.form['camera_ip']
    port = int(request.form['camera_port'])
    path = request.form['camera_path']
    new_username = request.form.get('camera_username')
    new_password = request.form.get('camera_password')
    location = request.form.get('camera_location')

    db = database.get_db()
    camera = db.execute('SELECT * FROM cameras WHERE id = ?', (camera_id,)).fetchone()

    if not camera:
        return "Camera not found", 404

    # Use new credentials if provided, otherwise use existing ones
    username = new_username if new_username else camera['username']
    password = new_password if new_password else camera['password']

    camera_url = f'rtsp://{username}:{password}@{ip}:{port}/{path}'

    if validate_rtsp(camera_url):
        db.execute('UPDATE cameras SET ip = ?, port = ?, path = ?, username = ?, password = ?, location = ? WHERE id = ?',
                   (ip, port, path, username, password, location, camera_id))
        db.commit()
        logging.debug(f"RTSP camera updated successfully with URL: {camera_url}")
    else:
        logging.error("Invalid RTSP camera URL or stream error")
        return 'Invalid RTSP camera URL or stream error', 400

    return redirect(url_for('index'))

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']

        user = get_user(session['username'])
        if user and check_password(user['password'], old_password):
            update_password(session['username'], new_password)
            session.pop('logged_in', None)  # Log out the user automatically
            session.pop('username', None)
            return redirect(url_for('login'))
        return 'Incorrect old password', 400

    return render_template('change_password.html')

@app.route('/user_management')
def user_management():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    db = database.get_db()
    users = db.execute('SELECT * FROM users').fetchall()
    return render_template('user_management.html', users=users)

@app.route('/overview')
def overview():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    return redirect(url_for('index'))

if __name__ == '__main__':
    # Ensure the database schema is initialized
    with app.app_context():
        if not os.path.exists(str(os.environ.get('DB_NAME', 'app.db'))):
            database.init_db()

    # Get the port from environment variable or use default 5000
    port = int(os.environ.get('PORT', 5000))
    
    # Run the app on the configured port
    app.run(debug=True, port=port)
