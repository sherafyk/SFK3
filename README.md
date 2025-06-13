# SFK Document Table Extractor

A simple web app for uploading field document images and extracting arrival and departure condition tables using OpenAI Vision.

## Features
- Password-protected login (`API2025` by default)
- Drag & drop multi-upload with previews
- Images stored with UTC timestamp names
- Calls OpenAI Vision API (`o4-mini` by default)
- Shows markdown and rendered table output
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
2. Build and run with Docker:
```bash
docker-compose up -d --build
```
3. Visit `http://localhost:5000` and login with the password.

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



