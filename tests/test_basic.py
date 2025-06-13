import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
import os
import tempfile
import pytest
from app.main import app, init_db

@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    app.config['DATABASE'] = db_path
    app.config['TESTING'] = True
    init_db()
    with app.test_client() as client:
        yield client
    os.close(db_fd)
    os.unlink(db_path)


def test_login(client):
    rv = client.post('/', data={'password': 'API2025'}, follow_redirects=True)
    assert b'Upload Images' in rv.data
