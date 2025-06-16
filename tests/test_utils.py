import sys, pathlib, json
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from unittest.mock import patch, MagicMock, ANY
from backend.utils import call_openai_json, markdown_looks_like_json, MODEL
import os


def test_call_openai_json_valid_json():
    os.environ['OPENAI_API_KEY'] = 'test'
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content='{"foo": "bar"}'))]
    with patch('backend.utils.openai.chat.completions.create', return_value=mock_resp) as mock_create:
        result = call_openai_json('tables')
        json_obj = json.loads(result)  # Should not raise
        assert json_obj == {"foo": "bar"}
        mock_create.assert_called_once_with(
            model=MODEL,
            messages=[{"role": "user", "content": ANY}],
            response_format={"type": "json_object"},
            temperature=0,
        )


def test_markdown_looks_like_json():
    good = '{"arrival_tanks": [], "departure_tanks": [], "products": [], "time_log": [], "draft_readings": []}'
    bad = 'not json'
    assert markdown_looks_like_json(good)
    assert not markdown_looks_like_json(bad)
