import os
import json
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    send_from_directory,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from redis import Redis
from redis.exceptions import RedisError
from flask_wtf import CSRFProtect
from passlib.hash import argon2
from dotenv import load_dotenv
from functools import wraps

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
from backend.bdr_extractor import (
    BDR_PROMPT,
    extract_bdr,
    merge_bdr_json,
    _extract_json,
    call_openai_bdr_json,
)
from backend.models import (
    init_db,
    log_request,
    get_job_name,
    set_job_name,
    add_attachment,
    get_attachments,
)
from pathlib import Path
from backend.cleanup import purge_old_uploads
from backend import worker

APP_PASSWORD = os.getenv('APP_PASSWORD')
if not APP_PASSWORD:
    raise RuntimeError('APP_PASSWORD environment variable not set')
PASS_HASH = argon2.hash(APP_PASSWORD)
RATE_LIMIT_PER_HOUR = int(os.getenv('RATE_LIMIT_PER_HOUR', 50))
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

if REDIS_URL.startswith(('redis://', 'rediss://', 'unix://')):
    try:
        Redis.from_url(REDIS_URL).ping()
    except RedisError:
        REDIS_URL = 'memory://'

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


def login_required(func):
    """Redirect to login page when the user is not authenticated."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return func(*args, **kwargs)

    return wrapper


def job_db_path(job_id: str) -> str:
    """Return the SQLite path for the given job."""
    return os.path.join(UPLOAD_FOLDER, f"{job_id}.db")


def vision_pipeline(image_path: str, model: str | None = None):
    if model is None:
        model = MODEL
    prompt = generate_prompt()
    md = call_openai(image_path, prompt, os.path.basename(image_path), model)
    return prompt, md


@app.route('/', methods=['GET', 'POST'])
@limiter.limit(f"{RATE_LIMIT_PER_HOUR}/hour")
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
@login_required
def upload():
    if request.method == 'POST':
        if 'files' not in request.files:
            flash('No files part')
            return redirect(request.url)
        files = request.files.getlist('files')
        model = request.form.get('model') or MODEL
        session['model'] = model
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
                fut = worker.run_async(vision_pipeline, path, model)
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
        return render_template('result.html', results=results, model=model)
    model = session.get('model', MODEL)
    return render_template('upload.html', model=model)


@app.route('/retry/<filename>', methods=['POST'])
@limiter.limit(f"{RATE_LIMIT_PER_HOUR}/hour")
@login_required
def retry(filename):
    prompt = request.form.get('prompt', generate_prompt())
    model = request.form.get('model') or session.get('model', MODEL)
    session['model'] = model
    path = os.path.join(UPLOAD_FOLDER, filename)
    try:
        output_text = call_openai(path, prompt, filename, model)
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
    return render_template('result.html', results=[result], model=model)


@app.route('/json', methods=['POST'])
@limiter.limit(f"{RATE_LIMIT_PER_HOUR}/hour")
def to_json():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    markdown_tables = data.get('markdown', '')
    model = session.get('model', MODEL)
    try:
        json_text = call_openai_json(markdown_tables, model)
        json_text = enhance_tank_conditions(json_text)
        json_obj = json.loads(json_text)
        json_text = json.dumps(json_obj, indent=2)
    except Exception as e:
        json_text = str(e)
    return jsonify({'json': json_text})


@app.route('/history')
@login_required
def history():
    job_files = sorted(Path(UPLOAD_FOLDER).glob('*.db'), key=lambda p: p.stat().st_mtime, reverse=True)
    jobs = []
    for f in job_files:
        # Older job databases may predate the ``jobmeta`` table. ``init_db``
        # upgrades the schema in-place so querying ``jobmeta`` doesn't fail.
        init_db(str(f))
        with get_db(str(f)) as conn:
            row = conn.execute(
                "SELECT filename, timestamp, ip FROM requests ORDER BY id DESC LIMIT 1"
            ).fetchone()
            name_row = conn.execute("SELECT name FROM jobmeta").fetchone()
        if row:
            jobs.append({'job_id': f.stem, 'filename': row[0], 'timestamp': row[1], 'ip': row[2], 'job_name': name_row[0] if name_row else ''})
    return render_template('history.html', jobs=jobs)


@app.route('/delete_job/<job_id>', methods=['POST'])
@login_required
def delete_job(job_id):
    db_path = job_db_path(job_id)
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass
    flash('Job deleted')
    return redirect(url_for('history'))


@app.route('/job/<job_id>', methods=['GET', 'POST'])
@login_required
def job_detail(job_id):
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
        file = request.files.get('attachment')
        if file and file.filename:
            new_name, _ = save_file(file)
            add_attachment(new_name, db_path=db_path)
            flash('Attachment uploaded')
            return redirect(url_for('job_detail', job_id=job_id))

        new_name = request.form.get('job_name', '')
        set_job_name(new_name, db_path=db_path)
        with get_db(db_path) as conn:
            rows = conn.execute("SELECT id FROM requests").fetchall()
            for r in rows:
                pid = r[0]
                prompt_val = request.form.get(f'prompt_{pid}', '')
                output_val = request.form.get(f'output_{pid}', '')
                json_val = request.form.get(f'json_{pid}', '')
                bdr_json_val = request.form.get(f'bdr_json_{pid}', '')
                bdr_md_val = request.form.get(f'bdr_md_{pid}', '')
                conn.execute(
                    "UPDATE requests SET prompt=?, output=?, json=?, bdr_json=?, bdr_md=? WHERE id=?",
                    (
                        prompt_val,
                        output_val,
                        json_val,
                        bdr_json_val,
                        bdr_md_val,
                        pid,
                    ),
                )
        flash('Job updated')
        return redirect(url_for('job_detail', job_id=job_id))
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, filename, prompt, output, json, bdr_json, bdr_md FROM requests ORDER BY id"
        ).fetchall()
    job_name = get_job_name(db_path)
    rows = [
        {
            'id': r[0],
            'filename': r[1],
            'prompt': r[2],
            'output': r[3],
            'json': r[4],
            'bdr_json': r[5],
            'bdr_md': r[6],
        }
        for r in rows
    ]
    attachments = get_attachments(db_path)
    return render_template(
        'job_detail.html',
        job_id=job_id,
        rows=rows,
        job_name=job_name,
        attachments=attachments,
    )


@app.route('/update_json/<job_id>/<int:req_id>', methods=['POST'])
def update_json(job_id, req_id):
    """Update the stored JSON for a single request row."""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    json_text = data.get('json', '')
    try:
        json.loads(json_text)
    except json.JSONDecodeError as e:
        return jsonify({'error': 'Invalid JSON', 'message': str(e)}), 400

    db_path = job_db_path(job_id)
    if not os.path.exists(db_path):
        return jsonify({'error': 'Job not found'}), 404
    init_db(db_path)
    with get_db(db_path) as conn:
        conn.execute('UPDATE requests SET json=? WHERE id=?', (json_text, req_id))
    return jsonify({'status': 'ok'})


@app.route('/extract_bdr/<job_id>/<int:req_id>', methods=['POST'])
def extract_bdr_route(job_id, req_id):
    """Extract BDR tables from the original image and store the markdown."""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    db_path = job_db_path(job_id)
    if not os.path.exists(db_path):
        return jsonify({'error': 'Job not found'}), 404

    init_db(db_path)
    with get_db(db_path) as conn:
        row = conn.execute(
            'SELECT filename FROM requests WHERE id=?', (req_id,)
        ).fetchone()
    if not row:
        return jsonify({'error': 'Request not found'}), 404

    filename = row[0]
    model = session.get('model', MODEL)
    image_path = os.path.join(UPLOAD_FOLDER, filename)
    attachments = get_attachments(db_path)
    if attachments:
        # Use the most recent attachment when extracting BDR tables
        att_path = os.path.join(UPLOAD_FOLDER, attachments[-1]["filename"])
        if os.path.exists(att_path):
            image_path = att_path
            filename = attachments[-1]["filename"]
    try:
        output_text = call_openai(
            image_path,
            BDR_PROMPT,
            filename,
            model,
            crop_top_fraction=0.40,
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    html_output = convert_markdown(output_text)
    with get_db(db_path) as conn:
        conn.execute(
            'UPDATE requests SET bdr_md=? WHERE id=?',
            (output_text, req_id),
        )
    return jsonify({'bdr_md': output_text, 'html': html_output})


@app.route('/bdr_json/<job_id>/<int:req_id>', methods=['POST'])
def bdr_json_route(job_id, req_id):
    """Convert stored BDR tables to JSON and save the result."""
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    markdown_tables = data.get('markdown', '')
    if not markdown_tables:
        return jsonify({'error': 'No markdown supplied'}), 400

    model = session.get('model', MODEL)
    try:
        json_text = call_openai_bdr_json(markdown_tables, model)
        json_obj = json.loads(json_text)
        json_text = json.dumps(json_obj, indent=2)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    db_path = job_db_path(job_id)
    if not os.path.exists(db_path):
        return jsonify({'error': 'Job not found'}), 404
    init_db(db_path)
    with get_db(db_path) as conn:
        conn.execute(
            'UPDATE requests SET bdr_json=? WHERE id=?',
            (json_text, req_id),
        )
    return jsonify({'bdr_json': json_text})


@app.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    """Serve uploaded files from the uploads folder."""
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    port = int(os.getenv('PORT', 57701))
    app.run(host='0.0.0.0', port=port)
