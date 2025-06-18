import sys, pathlib, os, re, tempfile
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

UPLOAD_DIR = tempfile.mkdtemp()
os.environ.setdefault('UPLOAD_FOLDER', UPLOAD_DIR)
os.environ.setdefault('REDIS_URL', 'memory://')
os.environ.setdefault('APP_PASSWORD', 'API2025')

from backend.app import app
from backend.models import init_db
import pytest

@pytest.fixture
def csrf_client():
    db_dir = UPLOAD_DIR
    os.environ['UPLOAD_FOLDER'] = db_dir
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = True
    from backend.app import limiter
    limiter.reset()
    os.makedirs(db_dir, exist_ok=True)
    init_db(os.path.join(db_dir, 'requests.db'))
    with app.test_client() as client:
        yield client
    for f in os.listdir(db_dir):
        os.remove(os.path.join(db_dir, f))
    os.rmdir(db_dir)

def test_login_csrf(csrf_client):
    rv = csrf_client.get('/')
    m = re.search(r'name="csrf_token" value="([^"]+)"', rv.data.decode())
    assert m, 'CSRF token not found'
    token = m.group(1)
    rv = csrf_client.post('/', data={'password': 'API2025', 'csrf_token': token}, follow_redirects=True)
    assert b'Upload Images' in rv.data
