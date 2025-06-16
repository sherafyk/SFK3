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
    convert_markdown,
    UPLOAD_FOLDER,
    MODEL,
    MAX_FILE_SIZE_MB,
)
from backend.models import init_db, log_request
from backend import worker

LOGIN_PASSWORD = os.getenv('LOGIN_PASSWORD', 'API2025')
RATE_LIMIT_PER_HOUR = int(os.getenv('RATE_LIMIT_PER_HOUR', 50))
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")
app = Flask(__name__, template_folder=FRONTEND_DIR, static_folder=FRONTEND_DIR)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=REDIS_URL,
    default_limits=[f"{RATE_LIMIT_PER_HOUR}/hour"],
)
limiter.init_app(app)

init_db()


def vision_pipeline(image_path: str):
    prompt = generate_prompt()
    output_text = call_openai(image_path, prompt, os.path.basename(image_path))
    return prompt, output_text


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == LOGIN_PASSWORD:
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
                job_id = generate_job_id()
                log_request(new_name, request.remote_addr, prompt, output_text)
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
    log_request(filename, request.remote_addr, prompt, output_text)
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
    except Exception as e:
        json_text = str(e)
    return jsonify({'json': json_text})


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    port = int(os.getenv('PORT', 57701))
    app.run(host='0.0.0.0', port=port)
