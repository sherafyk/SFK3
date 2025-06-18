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
1. Install the Python dependencies so you can run the app and tests.
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # adds pytest and other dev tools
```
2. Copy `.env.example` to `.env` and update values.
```
cp .env.example .env
```
If you are running the app without HTTPS (e.g., on localhost), set
`SESSION_COOKIE_SECURE=False` in your `.env` file so the login session works.
Redis is used to persist rate-limit state. Ensure `REDIS_URL` points to your
Redis server (for Docker Compose this is typically `redis://redis:6379`). If no
Redis server is reachable, the app falls back to an in-memory limiter.
3. Build and run with Docker:
```bash
docker-compose up -d --build
```
4. Visit `http://localhost:57701` and login with the password.

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
3. Review the rendered tables below. Each table cell uses an input box so you can correct the values before exporting.
4. If the output still needs tweaking, edit the prompt and hit **Edit & Retry**.

## Testing
Install dependencies and run pytest:
```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```
## Updating

Pull the latest changes and rebuild:
```
docker-compose down
```
```bash
git pull
docker-compose up -d --build
```
### Additional diagnostic checks

```
docker ps
```
```
docker logs sfk3-app-1 --tail=100
```




