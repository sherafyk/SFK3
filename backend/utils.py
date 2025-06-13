import os
import datetime
import base64
from werkzeug.utils import secure_filename
import openai
from markdown2 import markdown

UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', os.path.join('backend', 'data'))
ALLOWED_EXTENSIONS = set(os.getenv('ALLOWED_EXTENSIONS', 'png,jpg,jpeg,webp').split(','))
MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', 8))
MODEL = os.getenv('MODEL', 'o4-mini')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
openai.api_key = os.getenv('OPENAI_API_KEY')


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_file(file):
    now = datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[1].lower()
    new_name = f"{now}.{ext}"
    path = os.path.join(UPLOAD_FOLDER, new_name)
    file.save(path)
    return new_name, path


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
    with open(path, 'rb') as f:
        ext = filename.rsplit('.', 1)[1].lower()
        b64 = base64.b64encode(f.read()).decode()
        response = openai.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/{ext};base64,{b64}"}},
                    ],
                }
            ],
        )
    return response.choices[0].message.content


def convert_markdown(md: str) -> str:
    return markdown(md)
