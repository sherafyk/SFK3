# SFK Document Table Extractor

A simple web app for uploading field document images and extracting arrival and departure condition tables using OpenAI Vision.

## Features
- Password-protected login (`API2025` by default)
- Drag & drop multi-upload with previews
- Images stored with UTC timestamp names
- Calls OpenAI Vision API (`o4-mini` by default)
- Shows markdown and rendered table output
- Copy or download markdown results
- Edit the prompt and retry extraction
- Stores request logs in SQLite
- Rate limited to 50 uploads/hour per IP

## Setup
```
git clone https://github.com/sherafyk/SFK3.git
```
```
cd SFK3
```
1. Copy `.env.example` to `.env` and update values.
```
cp .env.example .env
```
2. Build and run with Docker:
```bash
docker-compose up -d --build
```
3. Visit `http://localhost:5000` and login with the password.

## Structure

```
.
├── backend/
│   ├── app.py
│   ├── models.py
│   ├── utils.py
│   └── ...
├── frontend/
│   ├── index.html
│   ├── upload.html
│   ├── result.html
│   ├── main.js
│   └── style.css
```

## Usage
1. Drag and drop or select one or more image files (png/jpg/webp ≤8MB).
2. After processing, copy or download the markdown tables.
3. If the output needs tweaking, edit the prompt and hit **Edit & Retry**.

## Testing
Install dependencies and run pytest:
```bash
pip install -r requirements.txt
pytest
```
## Updating

Pull the latest changes and rebuild:

```bash
git pull
docker-compose down
docker-compose up -d --build
```



