import sys, pathlib, json
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from unittest.mock import patch, MagicMock, ANY
from backend.utils import (
    call_openai_json,
    markdown_looks_like_json,
    enhance_tank_conditions,
    convert_markdown,
    MODEL,
)
import openai
import os
import math
import pytest


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


def test_enhance_tank_conditions():
    data = {
        "tankConditions": {
            "arrival": [
                {
                    "tank": "1",
                    "productName": "Prod",
                    "api": 10.0,
                    "ullageFt": 0,
                    "ullageIn": 0,
                    "tempF": 70.0,
                    "waterBbls": 0,
                    "grossBbls": 0,
                    "netBbls": 0,
                    "metricTons": 0,
                }
            ],
            "departure": [],
        },
        "productsDischarged": [],
        "eventTimeline": [],
        "draftReadings": [],
    }
    result = enhance_tank_conditions(json.dumps(data))
    obj = json.loads(result)
    tank = obj["tankConditions"]["arrival"][0]
    assert tank["changeTemp"] == 10.0
    assert tank["specificG"] == pytest.approx(1.0)
    assert tank["densityKgm3"] == pytest.approx(999.016)
    assert tank["alpha"] == pytest.approx(0.0003744427624)
    assert tank["exp"] == pytest.approx(math.e)
    assert tank["VCF"] == pytest.approx(0.99625139939)


def test_convert_markdown_sanitizes_script():
    md = "Bad<script>alert('x')</script>\n\n|A|B|\n|--|--|\n|1|2|"
    html = convert_markdown(md)
    assert "<script>" not in html
    assert "<table>" in html

