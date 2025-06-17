import sys, pathlib, json
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from unittest.mock import patch, MagicMock, ANY
from backend.utils import call_openai_json, markdown_looks_like_json, MODEL
import openai
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
        )


def test_call_openai_json_retry_without_temperature():
    os.environ['OPENAI_API_KEY'] = 'test'
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content='{"foo": "bar"}'))]
    error = openai.BadRequestError(
        message="bad",
        response=MagicMock(status_code=400, headers={}, request=None),
        body={"error": {"code": "unsupported_value", "param": "temperature"}},
    )
    with patch('backend.utils.MODEL', 'gpt-3.5'), patch(
        'backend.utils.openai.chat.completions.create',
        side_effect=[error, mock_resp],
    ) as mock_create:
        result = call_openai_json('tables')
        assert json.loads(result) == {"foo": "bar"}
        assert mock_create.call_count == 2
        first_args = mock_create.call_args_list[0].kwargs
        assert first_args['temperature'] == 1
        second_args = mock_create.call_args_list[1].kwargs
        assert 'temperature' not in second_args


def test_markdown_looks_like_json():
    good = '{"arrival_tanks": [], "departure_tanks": [], "products": [], "time_log": [], "draft_readings": []}'
    bad = 'not json'
    assert markdown_looks_like_json(good)
    assert not markdown_looks_like_json(bad)
