import os
import uuid
import datetime
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.utils import secure_filename
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
import openai

load_dotenv()

UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'data')
ALLOWED_EXTENSIONS = set(os.getenv('ALLOWED_EXTENSIONS', 'png,jpg,jpeg,webp').split(','))
MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', 8))
LOGIN_PASSWORD = os.getenv('LOGIN_PASSWORD', 'API2025')
RATE_LIMIT_PER_HOUR = int(os.getenv('RATE_LIMIT_PER_HOUR', 50))
MODEL = os.getenv('MODEL', 'o4-mini')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))

limiter = Limiter(key_func=get_remote_address, default_limits=[f"{RATE_LIMIT_PER_HOUR}/hour"])
limiter.init_app(app)

DATABASE = os.path.join(UPLOAD_FOLDER, 'requests.db')


def init_db():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            timestamp TEXT,
            ip TEXT,
            prompt TEXT,
            output TEXT
        )"""
    )
    conn.commit()
    conn.close()


init_db()


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_file(file):
    now = datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[1].lower()
    new_name = f"{now}.{ext}"
    path = os.path.join(UPLOAD_FOLDER, new_name)
    file.save(path)
    return new_name, path


def log_request(filename, ip, prompt, output):
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO requests (filename, timestamp, ip, prompt, output) VALUES (?, ?, ?, ?, ?)",
        (filename, datetime.datetime.utcnow().isoformat(), ip, prompt, output),
    )
    conn.commit()
    conn.close()


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == LOGIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('upload'))
        flash('Incorrect password')
    return render_template('login.html')


def generate_prompt():
    return (
        "Please analyze the attached image and extract the tank data as two separate tables, in markdown format:\n"
        "- The first table should show arrival conditions.\n"
        "- The second table should show departure conditions.\n"
        "\n"
        "Each table should list all individual tanks and use the following columns (with these exact headers):\n"
        "| Tank | Product Name | API | Ullage (Ft) | Ullage (in) | Temp (°F) | Water (Bbls) | Gross Bbls | Net Bbls | Metric Tons |\n"
        "| ---- | ------------ | --- | ----------- | ----------- | --------- | ------------ | ---------- | -------- | ----------- |\n"
        "\nIf a value is missing or unclear, leave the cell blank.\n"
        "Output only the two markdown tables: one for arrival, one for departure.\n"
    )


@app.route('/upload', methods=['GET', 'POST'])
@limiter.limit(f"{RATE_LIMIT_PER_HOUR}/hour")
def upload():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        if 'files' not in request.files:
            flash('No files part')
            return redirect(request.url)
        files = request.files.getlist('files')
        results = []
        for file in files:
            if file and allowed_file(file.filename):
                if len(file.read()) > MAX_FILE_SIZE_MB * 1024 * 1024:
                    flash(f"{file.filename} exceeds size limit")
                    continue
                file.seek(0)
                new_name, path = save_file(file)
                prompt = generate_prompt()
                try:
                    with open(path, 'rb') as f:
                        response = openai.chat.completions.create(
                            model=MODEL,
                            messages=[
                                {"role": "user", "content": prompt},
                                {"role": "user", "content": {"type": "image", "data": f.read()}},
                            ],
                        )
                    output_text = response.choices[0].message.content
                except Exception as e:
                    output_text = str(e)
                job_id = f"{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M')}-{uuid.uuid4().hex[:5].upper()}"
                log_request(new_name, request.remote_addr, prompt, output_text)
                results.append({'filename': new_name, 'output': output_text, 'job_id': job_id})
            else:
                flash(f"Invalid file: {file.filename}")
        return render_template('result.html', results=results)
    return render_template('upload.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
