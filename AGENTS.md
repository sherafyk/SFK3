## 1  Move blocking Vision & JSON calls off the Flask worker

1. **Add a tiny job-runner**

   ```python
   # backend/worker.py
   from concurrent.futures import ThreadPoolExecutor
   executor = ThreadPoolExecutor(max_workers=4)
   def run_async(func, *args, **kwargs):
       return executor.submit(func, *args, **kwargs)
   ```
2. **Refactor `process_images()` in `backend/app.py`**

   * Extract the loop that:

     * pre-processes the image →
     * calls `openai.chat.completions` (Markdown) →
     * optionally calls the JSON formatter
       into a pure function `def vision_pipeline(image_path): ...`.
   * In the `/upload` route, replace the direct call with:

     ```python
     fut = worker.run_async(vision_pipeline, img_path)
     result = fut.result()      # blocks, but the heavy work is now on a thread
     ```
3. **Done-when**

   * A single upload no longer blocks other requests (test with two curl uploads in parallel; both return without queueing).
   * No change to HTML output.

---

## 2  Lightweight client-side image shrink

1. **Frontend (`static/js/upload.js`)**

   ```javascript
   // before adding file to FormData:
   const img = await createImageBitmap(file);
   const canvas = new OffscreenCanvas(Math.min(img.width, 1024), Math.min(img.height, 1024));
   const ctx = canvas.getContext('2d');
   ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
   const blob = await canvas.convertToBlob({ type: 'image/jpeg', quality: 0.8 });
   formData.append('files', new File([blob], file.name, { type: 'image/jpeg' }));
   ```
2. **Keep server-side path unchanged** – accept JPEG/PNG exactly as before.
3. **Done-when**

   * Network payload per image ≤ 300 KB for a 3000×4000 photo.
   * The original preprocessing still succeeds.

---

## 3  Switch SQLite to WAL & add filename collision guard

1. **`backend/utils.py`**

   ```python
   import sqlite3
   def get_db():
       conn = sqlite3.connect(DB_PATH, check_same_thread=False)
       conn.execute('PRAGMA journal_mode=WAL;')
       return conn
   ```
2. **`backend/app.py` – save path**

   ```python
   fname = f"{datetime.utcnow():%Y%m%d%H%M%S}_{uuid4().hex[:8]}.jpg"
   ```
3. **Done-when**

   * Parallel uploads (>2 at once) no longer show “database is locked”.
   * Duplicate-time uploads produce unique filenames.

---

## 4  Persist rate-limit state with Redis

1. **Install** `pip install redis`
2. **`backend/app.py`**

   ```python
   from flask_limiter.util import get_remote_address
   from flask_limiter import Limiter
   from redis import Redis
   limiter = Limiter(
       key_func=get_remote_address,
       storage_uri="redis://localhost:6379",  # pull from .env
   )
   ```
3. **Docker-compose**: add a `redis` service.
4. **Done-when**

   * Restarting the container does **not** reset remaining quota.

---

## 5  Skip second model call when Markdown is already spec-compliant

1. **`backend/utils.py`**

   ```python
   import json, re
   SCHEMA_KEYS = {"arrival_tanks", "departure_tanks", "products", "time_log", "draft_readings"}
   def markdown_looks_like_json(md: str) -> bool:
       try:
           obj = json.loads(md)
           return SCHEMA_KEYS <= obj.keys()
       except json.JSONDecodeError:
           return False
   ```
2. **In `vision_pipeline()`**

   ```python
   md = call_vision(...)
   if markdown_looks_like_json(md):
       return md              # already JSON
   json_out = call_json_formatter(md)
   return json_out
   ```
3. **Done-when**

   * Upload a pristine template image: only one OpenAI request appears in logs.
   * Legacy images still trigger both calls and give identical JSON to pre-change output.

---

## 6  Base64 encode without extra memory copy

1. **Replace** in `utils.py`

   ```python
   buf = io.BytesIO()
   img.save(buf, format="PNG")
   b64 = base64.b64encode(buf.getvalue()).decode()
   ```
2. **Done-when**

   * Peak RSS per worker drops by \~30-40 MB during 5-image upload (check with `/proc/<pid>/status`).

---

## 7  Security hardening quick-wins

1. **Config**

   ```python
   MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB
   SESSION_COOKIE_SECURE = True
   ```
2. **Enable CSRF**

   ```python
   from flask_wtf import CSRFProtect
   CSRFProtect(app)
   ```
3. **Hash password** (keep route unchanged)

   ```python
   from passlib.hash import argon2
   # during startup:
   PASS_HASH = argon2.hash(os.environ['APP_PASSWORD'])
   # on login:
   if argon2.verify(submitted_pw, PASS_HASH): ...
   ```
4. **Done-when**

   * Oversized POST returns HTTP 413.
   * CSRF token present in hidden form field.

---

## 8  Dead-file garbage collection

1. **Add cron-like cleaner** (`backend/cleanup.py`)

   ```python
   def purge_old_uploads(days=7):
       cutoff = datetime.utcnow() - timedelta(days=days)
       for p in UPLOAD_DIR.iterdir():
           if p.stat().st_mtime < cutoff.timestamp():
               p.unlink(missing_ok=True)
   ```
2. **Call** from `app.py` on startup, or schedule via docker-compose `command: ["bash","-c","python -m backend.cleanup && gunicorn ..."]`.
3. **Done-when**

   * Running `purge_old_uploads()` locally deletes week-old test files, leaving fresh ones untouched.

---

## 9  Pin dependency versions

Create `requirements.lock`:

```
Flask==3.0.3
flask-limiter==3.5.1
Pillow==10.2.0
openai==1.24.0
passlib==1.7.4
redis==5.0.4
```

Add to Docker build:

```dockerfile
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
```

**Done-when** a fresh build produces identical `pip freeze`.

---

### Final “green-path” test

```bash
# 1. docker-compose up --build
# 2. curl -F files=@sample.jpg http://localhost:57701/upload -u "demo:API2025"
# 3. Verify:
#    • HTTP 200 with Markdown & JSON rendered
#    • Two simultaneous curls return without 500/429
#    • Redis shows key `limiter/<ip>`
#    • Older uploads auto-purged after cron run
```

Implementing these nine tasks preserves all existing functionality while removing the main performance, reliability and security pain-points.
