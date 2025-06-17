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


def test_job_detail_upgrades_schema(client, tmp_path):
    """Older job databases without the ``json`` column should be upgraded"""
    import sqlite3
    from pathlib import Path
    from backend.utils import UPLOAD_FOLDER

    client.post('/', data={'password': 'API2025'}, follow_redirects=True)

    db_path = Path(UPLOAD_FOLDER) / 'old.db'
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            timestamp TEXT,
            ip TEXT,
            prompt TEXT,
            output TEXT
        )"""
    )
    conn.execute(
        "INSERT INTO requests (filename, timestamp, ip, prompt, output) VALUES (?,?,?,?,?)",
        ('f', 't', '1.1.1.1', 'p', 'o'),
    )
    conn.commit()
    conn.close()

    rv = client.get(f'/job/{db_path.stem}')
    assert rv.status_code == 200
    assert b'f' in rv.data
    with sqlite3.connect(db_path) as conn_check:
        cols = [r[1] for r in conn_check.execute('PRAGMA table_info(requests)')]
    assert 'json' in cols


def test_delete_job(client, tmp_path):
    client.post('/', data={'password': 'API2025'}, follow_redirects=True)
    from pathlib import Path
    from backend.utils import UPLOAD_FOLDER
    from backend.models import init_db

    db_path = Path(UPLOAD_FOLDER) / 'del.db'
    init_db(str(db_path))

    rv = client.post(f'/delete_job/{db_path.stem}', follow_redirects=True)
    assert rv.status_code == 200
    assert not db_path.exists()
