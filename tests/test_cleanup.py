import sys, pathlib, os
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from datetime import datetime, timedelta
import importlib


def test_purge_old_uploads(tmp_path, monkeypatch):
    old_file = tmp_path / 'old.txt'
    new_file = tmp_path / 'new.txt'
    old_file.write_text('x')
    new_file.write_text('y')
    old_time = (datetime.utcnow() - timedelta(days=8)).timestamp()
    os.utime(old_file, (old_time, old_time))
    monkeypatch.setenv('UPLOAD_FOLDER', str(tmp_path))
    from backend import utils, cleanup
    importlib.reload(utils)
    importlib.reload(cleanup)
    cleanup.purge_old_uploads(days=7)
    assert not old_file.exists()
    assert new_file.exists()
