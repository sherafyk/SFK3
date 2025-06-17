import os
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from redis import Redis
from flask_wtf import CSRFProtect
from passlib.hash import argon2
from dotenv import load_dotenv

load_dotenv()

from backend.utils import (
    allowed_file,
    save_file,
    get_file_size,
    generate_prompt,
    generate_job_id,
    call_openai,
    call_openai_json,
    enhance_tank_conditions,
    convert_markdown,
    UPLOAD_FOLDER,
    MODEL,
    MAX_FILE_SIZE_MB,
    get_db,
)
from backend.models import init_db, log_request
from pathlib import Path
from backend.cleanup import purge_old_uploads
from backend import worker

PASS_HASH = argon2.hash(os.environ['APP_PASSWORD'])
RATE_LIMIT_PER_HOUR = int(os.getenv('RATE_LIMIT_PER_HOUR', 50))
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")
app = Flask(__name__, template_folder=FRONTEND_DIR, static_folder=FRONTEND_DIR)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024
app.config['SESSION_COOKIE_SECURE'] = (
    os.getenv('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
)
CSRFProtect(app)

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=REDIS_URL,
    default_limits=[f"{RATE_LIMIT_PER_HOUR}/hour"],
)
limiter.init_app(app)

init_db()
purge_old_uploads()


def job_db_path(job_id: str) -> str:
    """Return the SQLite path for the given job."""
    return os.path.join(UPLOAD_FOLDER, f"{job_id}.db")


def vision_pipeline(image_path: str):
    prompt = generate_prompt()
    md = call_openai(image_path, prompt, os.path.basename(image_path))
    return prompt, md


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        submitted_pw = request.form.get('password', '')
        if argon2.verify(submitted_pw, PASS_HASH):
            session['logged_in'] = True
            return redirect(url_for('upload'))
        flash('Incorrect password')
    return render_template('login.html')


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
        job_id = generate_job_id()
        job_path = job_db_path(job_id)
        init_db(job_path)
        for file in files:
            if file and allowed_file(file.filename):
                if get_file_size(file) > MAX_FILE_SIZE_MB * 1024 * 1024:
                    flash(f"{file.filename} exceeds size limit")
                    continue
                file.seek(0)
                new_name, path = save_file(file)
                fut = worker.run_async(vision_pipeline, path)
                try:
                    prompt, output_text = fut.result()
                except Exception as e:
                    prompt, output_text = generate_prompt(), str(e)
                log_request(
                    new_name,
                    request.remote_addr,
                    prompt,
                    output_text,
                    db_path=job_path,
                )
                html_output = convert_markdown(output_text)
                results.append(
                    {
                        'filename': new_name,
                        'output': output_text,
                        'html': html_output,
                        'job_id': job_id,
                        'prompt': prompt,
                    }
                )
            else:
                flash(f"Invalid file: {file.filename}")
        return render_template('result.html', results=results)
    return render_template('upload.html', model=MODEL)


@app.route('/retry/<filename>', methods=['POST'])
@limiter.limit(f"{RATE_LIMIT_PER_HOUR}/hour")
def retry(filename):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    prompt = request.form.get('prompt', generate_prompt())
    path = os.path.join(UPLOAD_FOLDER, filename)
    try:
        output_text = call_openai(path, prompt, filename)
    except Exception as e:
        output_text = str(e)
    job_id = generate_job_id()
    job_path = job_db_path(job_id)
    init_db(job_path)
    log_request(
        filename,
        request.remote_addr,
        prompt,
        output_text,
        db_path=job_path,
    )
    html_output = convert_markdown(output_text)
    result = {
        'filename': filename,
        'output': output_text,
        'html': html_output,
        'job_id': job_id,
        'prompt': prompt,
    }
    return render_template('result.html', results=[result])


@app.route('/json', methods=['POST'])
@limiter.limit(f"{RATE_LIMIT_PER_HOUR}/hour")
def to_json():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    markdown_tables = data.get('markdown', '')
    try:
        json_text = call_openai_json(markdown_tables)
        json_text = enhance_tank_conditions(json_text)
    except Exception as e:
        json_text = str(e)
    return jsonify({'json': json_text})


@app.route('/history')
def history():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    job_files = sorted(Path(UPLOAD_FOLDER).glob('*.db'), key=lambda p: p.stat().st_mtime, reverse=True)
    jobs = []
    for f in job_files:
        with get_db(str(f)) as conn:
            row = conn.execute(
                "SELECT filename, timestamp, ip FROM requests ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row:
            jobs.append({'job_id': f.stem, 'filename': row[0], 'timestamp': row[1], 'ip': row[2]})
    return render_template('history.html', jobs=jobs)


@app.route('/job/<job_id>', methods=['GET', 'POST'])
def job_detail(job_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    db_path = job_db_path(job_id)
    if not os.path.exists(db_path):
        return (
            render_template(
                "error.html",
                message="Job not found",
            ),
            404,
        )
    # Ensure database schema is up to date (older jobs may lack the ``json``
    # column).  ``init_db`` will create the table if needed and add the column
    # when missing.
    init_db(db_path)

    if request.method == 'POST':
        with get_db(db_path) as conn:
            rows = conn.execute("SELECT id FROM requests").fetchall()
            for r in rows:
                pid = r[0]
                prompt_val = request.form.get(f'prompt_{pid}', '')
                output_val = request.form.get(f'output_{pid}', '')
                json_val = request.form.get(f'json_{pid}', '')
                conn.execute(
                    "UPDATE requests SET prompt=?, output=?, json=? WHERE id=?",
                    (
                        prompt_val,
                        output_val,
                        json_val,
                        pid,
                    ),
                )
        flash('Job updated')
        return redirect(url_for('job_detail', job_id=job_id))
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, filename, prompt, output, json FROM requests ORDER BY id"
        ).fetchall()
    rows = [
        {
            'id': r[0],
            'filename': r[1],
            'prompt': r[2],
            'output': r[3],
            'json': r[4],
        }
        for r in rows
    ]
    return render_template('job_detail.html', job_id=job_id, rows=rows)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    port = int(os.getenv('PORT', 57701))
    app.run(host='0.0.0.0', port=port)
