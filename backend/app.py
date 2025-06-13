import os
import uuid
import datetime
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

from backend.utils import (
    allowed_file,
    save_file,
    generate_prompt,
    call_openai,
    convert_markdown,
    UPLOAD_FOLDER,
    MODEL,
    MAX_FILE_SIZE_MB,
)
from backend.models import init_db, log_request

load_dotenv()
LOGIN_PASSWORD = os.getenv('LOGIN_PASSWORD', 'API2025')
RATE_LIMIT_PER_HOUR = int(os.getenv('RATE_LIMIT_PER_HOUR', 50))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")
app = Flask(__name__, template_folder=FRONTEND_DIR, static_folder=FRONTEND_DIR)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))

limiter = Limiter(key_func=get_remote_address, default_limits=[f"{RATE_LIMIT_PER_HOUR}/hour"])
limiter.init_app(app)

init_db()


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
                if len(file.read()) > MAX_FILE_SIZE_MB * 1024 * 1024:
                    flash(f"{file.filename} exceeds size limit")
                    continue
                file.seek(0)
                new_name, path = save_file(file)
                prompt = generate_prompt()
                try:
                    output_text = call_openai(path, prompt, new_name)
                except Exception as e:
                    output_text = str(e)
                job_id = f"{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M')}-{uuid.uuid4().hex[:5].upper()}"
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
    job_id = f"{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M')}-{uuid.uuid4().hex[:5].upper()}"
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


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
