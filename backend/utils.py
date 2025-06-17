import os
import uuid
import datetime
import base64
import io
import shutil
import sqlite3
import json
import re
import math
from werkzeug.utils import secure_filename
import openai
from markdown2 import markdown
from PIL import Image, ImageOps

UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', os.path.join('backend', 'data'))
ALLOWED_EXTENSIONS = set(os.getenv('ALLOWED_EXTENSIONS', 'png,jpg,jpeg,webp').split(','))
MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', 8))
MODEL = os.getenv('MODEL', 'o4-mini')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
openai.api_key = os.getenv('OPENAI_API_KEY')

SCHEMA_KEYS = {"arrival_tanks", "departure_tanks", "products", "time_log", "draft_readings"}


def markdown_looks_like_json(md: str) -> bool:
    try:
        obj = json.loads(md)
        return SCHEMA_KEYS <= obj.keys()
    except json.JSONDecodeError:
        return False

# Database path shared across the app
DB_PATH = os.path.join(UPLOAD_FOLDER, 'requests.db')


def get_db(path: str = DB_PATH):
    """Return a SQLite connection to the given ``path``."""
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn


def get_file_size(file) -> int:
    """Return file size in bytes without reading the stream."""
    pos = file.stream.tell()
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(pos)
    return size


def generate_job_id() -> str:
    """Generate a UTC timestamped 5 character job ID."""
    return f"{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M')}-{uuid.uuid4().hex[:5].upper()}"


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_file(file):
    """Save an uploaded file to ``UPLOAD_FOLDER`` with a unique name."""
    now = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[1].lower()
    new_name = f"{now}_{uuid.uuid4().hex[:8]}.{ext}"
    path = os.path.join(UPLOAD_FOLDER, new_name)
    file.save(path)
    return new_name, path


def preprocess_image(path: str) -> None:
    """Convert image to grayscale and apply autocontrast in-place.

    The original image is preserved as ``<file>.orig`` so retries start
    from the unmodified source.
    """
    orig_path = f"{path}.orig"
    if not os.path.exists(orig_path):
        shutil.copy(path, orig_path)
    with Image.open(orig_path) as img:
        gray = ImageOps.grayscale(img)
        processed = ImageOps.autocontrast(gray)
        processed.save(path)


def generate_prompt() -> str:
    return (
        "Please analyze the attached image and extract the tank data as five separate tables, in markdown format:\n"
        "- The first table should show arrival conditions.\n"
        "- The second table should show departure conditions.\n"
        "\n"
        "The first and second table should list all individual tanks and use the following columns (with these exact headers):\n"
        "| Tank | Product Name | API | Ullage (Ft) | Ullage (in) | Temp (°F) | Water (Bbls) | Gross Bbls | Net Bbls | Metric Tons |\n"
        "| ---- | ------------ | --- | ----------- | ----------- | --------- | ------------ | ---------- | -------- | ----------- |\n"
        "\n"
        "- The third table should show products discharged totals, typically found at the bottom of the document.\n"
        "\n"
        "The third table should list all individual products and use the following columns (with these exact headers):\n"
        "| Product Discharged | API | Gross Bbls | Net Bbls | Metric Tons |\n"
        "| ------------------ | --- | ---------- | -------- | ----------- |\n"
        "\n"
        "- The fourth table should show the date and time log, typically found near the top right of the document.\n"
        "\n"
        "The fourth table should list all individual events and use the following columns (with these exact headers):\n"
        "| Event | Date | Time |\n"
        "| ----- | ---- | ---- |\n"
        "\n"
        "- The fifth table should show the arrival and departure drafts in decimal format, typically found on the right side of the document.\n"
        "\n"
        "The fifth table should combine and list the arrival and departure drafts, converting to decimal format if needed, using the following columns (with these exact headers):\n"
        "| Arrival/Departure | Fwd/Aft | Port | Stbd. |\n"
        "| ----------------- | ------- | ---- | ----- |\n"
        "\n"
        "\nIf a value is missing or unclear, leave the cell blank.\n"
        "Output only the five markdown tables: 1) Arrival Tank Values, 2) Departure Tank Values, 3) Products Discharged, 4) Time Log, 5) Draft Readings.\n"
    )


def call_openai(path: str, prompt: str, filename: str) -> str:
    try:
        preprocess_image(path)
        with Image.open(path) as img:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            ext = "png"
            b64 = base64.b64encode(buf.getbuffer()).decode()

        params = {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/{ext};base64,{b64}"},
                        },
                    ],
                }
            ],
        }
        if MODEL not in {"o3", "o3-mini", "o4-mini"}:
            params["temperature"] = 1

        try:
            response = openai.chat.completions.create(**params)
        except openai.BadRequestError as e:
            if (
                getattr(e, "body", None)
                and e.body.get("error", {}).get("code") == "unsupported_value"
                and e.body.get("error", {}).get("param") == "temperature"
            ):
                params.pop("temperature", None)
                response = openai.chat.completions.create(**params)
            else:
                raise RuntimeError(f"OpenAI API error: {e}") from e
        return response.choices[0].message.content
    except openai.OpenAIError as e:
        raise RuntimeError(f"OpenAI API error: {e}") from e


def convert_markdown(md: str) -> str:
    """Convert markdown text to HTML with table support."""
    return markdown(md, extras=["tables"])


JSON_PROMPT = """Please convert the tables below into a single JSON object that strictly follows this JSON Schema:

```
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "TankReport",
  "type": "object",
  "properties": {
    "tankConditions": {
      "type": "object",
      "properties": {
        "arrival": {
          "type": "array",
          "items": { "$ref": "#/definitions/tankCondition" }
        },
        "departure": {
          "type": "array",
          "items": { "$ref": "#/definitions/tankCondition" }
        }
      },
      "required": ["arrival", "departure"]
    },
    "productsDischarged": {
      "type": "array",
      "items": { "$ref": "#/definitions/productDischarged" }
    },
    "eventTimeline": {
      "type": "array",
      "items": { "$ref": "#/definitions/eventTimeline" }
    },
    "draftReadings": {
      "type": "array",
      "items": { "$ref": "#/definitions/draftReading" }
    }
  },
  "required": ["tankConditions", "productsDischarged", "eventTimeline", "draftReadings"],
  "definitions": {
    "tankCondition": {
      "type": "object",
      "properties": {
        "tank":         { "type": "string" },
        "productName":  { "type": "string" },
        "api":          { "type": "number" },
        "ullageFt":     { "type": "number" },
        "ullageIn":     { "type": "number" },
        "tempF":        { "type": "number" },
        "waterBbls":    { "type": "number" },
        "grossBbls":    { "type": "number" },
        "netBbls":      { "type": "number" },
        "metricTons":   { "type": "number" }
      },
      "required": ["tank", "productName", "api", "ullageFt", "ullageIn", "tempF", "waterBbls", "grossBbls", "netBbls", "metricTons"]
    },
    "productDischarged": {
      "type": "object",
      "properties": {
        "productName": { "type": "string" },
        "api":         { "type": "number" },
        "grossBbls":   { "type": "number" },
        "netBbls":     { "type": "number" },
        "metricTons":  { "type": "number" }
      },
      "required": ["productName", "api", "grossBbls", "netBbls", "metricTons"]
    },
    "eventTimeline": {
      "type": "object",
      "properties": {
        "event": { "type": "string" },
        "date":  { "type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$" },
        "time":  { "type": "string", "pattern": "^[0-9]{2}:[0-9]{2}$" }
      },
      "required": ["event", "date", "time"]
    },
    "draftReading": {
      "type": "object",
      "properties": {
        "event": { "type": "string" },
        "fwd": {
          "type": "object",
          "properties": {
            "port":  { "type": "number" },
            "stbd":  { "type": "number" }
          },
          "required": ["port", "stbd"]
        },
        "aft": {
          "type": "object",
          "properties": {
            "port":  { "type": "number" },
            "stbd":  { "type": "number" }
          },
          "required": ["port", "stbd"]
        }
      },
      "required": ["event", "fwd", "aft"]
    }
  }
}
```

Output only valid JSON."""


def call_openai_json(tables: str) -> str:
    """Convert extracted tables to JSON via a second model call.

    High-reasoning models such as ``o3`` and ``o4-mini`` ignore custom
    ``temperature`` values.  When using these models the parameter is omitted;
    otherwise ``temperature`` defaults to ``1``.  If the API still rejects the
    parameter, the call is retried without it.
    """

    message = tables + "\n\n" + JSON_PROMPT
    params = {
        "model": MODEL,
        "messages": [{"role": "user", "content": message}],
        "response_format": {"type": "json_object"},
    }
    if MODEL not in {"o3", "o3-mini", "o4-mini"}:
        params["temperature"] = 1

    try:
        response = openai.chat.completions.create(**params)
    except openai.BadRequestError as e:
        if (
            getattr(e, "body", None)
            and e.body.get("error", {}).get("code") == "unsupported_value"
            and e.body.get("error", {}).get("param") == "temperature"
        ):
            params.pop("temperature", None)
            response = openai.chat.completions.create(**params)
        else:
            raise RuntimeError(f"OpenAI API error: {e}") from e
    except openai.OpenAIError as e:
        raise RuntimeError(f"OpenAI API error: {e}") from e

    return response.choices[0].message.content


def enhance_tank_conditions(json_text: str) -> str:
    """Add calculated fields to each tank in the JSON structure.

    Parameters
    ----------
    json_text: str
        JSON string following the TankReport schema.

    Returns
    -------
    str
        Updated JSON string with additional calculated fields for each tank.
    """

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        return json_text

    tank_conditions = data.get("tankConditions", {})
    for phase in ("arrival", "departure"):
        tanks = tank_conditions.get(phase, [])
        if not isinstance(tanks, list):
            continue
        for tank in tanks:
            try:
                temp_f = float(tank.get("tempF", 0))
                api = float(tank.get("api", 0))
            except (TypeError, ValueError):
                # Skip tanks with invalid numeric values
                continue

            change_temp = temp_f - 60
            specific_g = 141.5 / (api + 131.5) if (api + 131.5) != 0 else 0
            density = specific_g * 999.016
            if density != 0:
                alpha = (103.8720 / (density ** 2)) + (0.2701 / density)
            else:
                alpha = 0
            vcf = math.exp(-alpha * change_temp * (1 + 0.8 * alpha * change_temp))

            tank["changeTemp"] = change_temp
            tank["specificG"] = specific_g
            tank["densityKgm3"] = density
            tank["alpha"] = alpha
            tank["exp"] = math.e
            tank["VCF"] = vcf

    return json.dumps(data)
