import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
import os
import tempfile
import pytest

UPLOAD_DIR = tempfile.mkdtemp()
os.environ.setdefault('UPLOAD_FOLDER', UPLOAD_DIR)
os.environ.setdefault('REDIS_URL', 'memory://')
os.environ.setdefault('APP_PASSWORD', 'API2025')
from backend.app import app
from backend.models import init_db

@pytest.fixture
def client():
    db_dir = UPLOAD_DIR
    os.environ['UPLOAD_FOLDER'] = db_dir
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    os.makedirs(db_dir, exist_ok=True)
    init_db()
    with app.test_client() as client:
        yield client
    for f in os.listdir(db_dir):
        os.remove(os.path.join(db_dir, f))
    os.rmdir(db_dir)


def test_login(client):
    rv = client.post('/', data={'password': 'API2025'}, follow_redirects=True)
    assert b'Upload Images' in rv.data


def test_preprocess_image(tmp_path):
    from backend.utils import preprocess_image
    from PIL import Image

    img_path = tmp_path / 'color.png'
    Image.new('RGB', (10, 10), 'red').save(img_path)
    preprocess_image(str(img_path))
    processed = Image.open(img_path)
    assert processed.mode == 'L'
    assert (img_path.with_suffix(img_path.suffix + '.orig')).exists()


def test_log_request_saves_json(tmp_path):
    from backend.models import init_db, log_request
    from backend.utils import get_db

    db = tmp_path / 't.db'
    init_db(str(db))
    log_request('f', '1.1.1.1', 'p', 'o', db_path=str(db), json_text='{"a":1}')
    with get_db(str(db)) as conn:
        row = conn.execute('SELECT json FROM requests').fetchone()
    assert row[0] == '{"a":1}'


def test_job_detail_missing_db(client):
    client.post('/', data={'password': 'API2025'}, follow_redirects=True)
    rv = client.get('/job/doesnotexist')
    assert rv.status_code == 404
    assert b'Job not found' in rv.data
