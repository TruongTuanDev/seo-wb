# Seller WB AI Backend

FastAPI backend for the flow:

1. User registers/logs in.
2. User creates a store with a Wildberries Content API key.
3. User uploads product images and prompt.
4. Gemini extracts product features.
5. OpenAI/fallback generator creates a Wildberries card draft.
6. Frontend edits the draft.
7. Backend validates and pushes the card to Wildberries.
8. Optional Redis-backed image generation creates product-card media and attaches it to the draft.

Wildberries card creation is asynchronous. Images are not part of `/content/v2/cards/upload`; upload media after WB returns/creates an `nmID`.

## Run

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python .\scripts\migrate.py
uvicorn app.main:app --reload
```

Run the image generation worker in a second terminal when using AI-generated media:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.workers.image_generation_worker
```

Run the RabbitMQ sync worker for card push, product sync, and finance sync:

```powershell
python -m app.workers.wb_sync_worker
```

## Database

Default local database is PostgreSQL:

```text
postgresql+psycopg://postgres:12345678@127.0.0.1:5432/seo_wb_db
```

Create the database locally if it does not exist:

```sql
CREATE DATABASE seo_wb_db;
```

Run migrations:

```powershell
cd backend
python .\scripts\migrate.py
```

Deployment should run the same command before starting `uvicorn` or the ASGI server.

The app no longer creates tables automatically by default. Set `DB_AUTO_CREATE=true` only for temporary local experiments; production and deploy environments should use Alembic migrations.

Create a new migration after model changes:

```powershell
cd backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Important endpoints

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/stores`
- `GET /api/v1/stores`
- `POST /api/v1/cards/generate`
- `POST /api/v1/cards/drafts/{draft_id}/image-generation/jobs`
- `GET /api/v1/cards/drafts/{draft_id}/image-generation/jobs/{job_id}`
- `GET /api/v1/cards/drafts/{draft_id}`
- `PUT /api/v1/cards/drafts/{draft_id}`
- `POST /api/v1/cards/drafts/{draft_id}/push`
- `POST /api/v1/cards/{nm_id}/media`
- `GET /api/v1/wb/subjects`
- `GET /api/v1/wb/subjects/{subject_id}/charcs`

## Wildberries API notes

- New cards: `POST /content/v2/cards/upload`, body is an array of groups `{subjectID, variants}`.
- Merge cards into existing imt: `POST /content/v2/cards/upload/add`, body `{imtID, cardsToAdd}`.
- Create cards are asynchronous; check `/content/v2/cards/error/list` if success response does not produce a card.
- Images are uploaded after a card has `nmID`: `/content/v3/media/file` or `/content/v3/media/save`.

## AI image generation

Image generation is asynchronous and Redis-backed.

API contract:

```http
POST /api/v1/cards/drafts/{draft_id}/image-generation/jobs
Content-Type: multipart/form-data
```

Fields:

- `store_id`: current store ID.
- `variant_id`: frontend variant/card ID.
- `variant_index`: index of the variant inside the draft payload.
- `quantity`: generated image count, from `1` to `10`.
- `metadata_json`: optional JSON object with `title`, `category`, `subjectName`, `brand`, `color`, `material`, and `description`.
- `front_image`: required JPG, PNG, or WEBP.
- `back_image`: required JPG, PNG, or WEBP.
- `model_image`: optional JPG, PNG, or WEBP.

Worker flow:

1. The API validates files, creates Redis job state, and enqueues the job ID in `image_generation_jobs`.
2. A per-card Redis lock prevents duplicate generation for the same `{user, draft, variant}` while a job is queued or processing.
3. `python -m app.workers.image_generation_worker` consumes the Redis queue.
4. The worker builds reusable OpenAI image prompts, generates images, saves them under `storage/image_jobs/{job_id}/output`, attaches generated media URLs to the draft, and marks the job `completed`.
5. The frontend polls the status endpoint and appends completed images into the active card gallery.

Environment:

```text
REDIS_URL=redis://127.0.0.1:6379/0
# Or for managed Redis fields:
# REDIS_HOST=host:port
# REDIS_USER=default
# REDIS_PASSWORD=...
# REDIS_SSL=false
OPENAI_API_KEY=...
OPENAI_IMAGE_MODEL=gpt-image-1
MAX_AI_PRODUCT_IMAGES=10
OPENAI_IMAGE_CONCURRENCY=2
OPENAI_IMAGE_RETRY_ATTEMPTS=3
GENERATED_IMAGE_JPEG_QUALITY=88
IMAGE_GENERATION_LOCK_TTL_SECONDS=1800
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
```

Use `REDIS_SSL=true` only when the provider endpoint explicitly requires TLS. Redis Cloud endpoints that match the basic StackExchange.Redis sample without `Ssl=true` should use `REDIS_SSL=false`.
Keep `OPENAI_IMAGE_CONCURRENCY` conservative. GPT Image rate limits include IPM (images per minute), so higher concurrency can improve latency only if your project tier has enough remaining image capacity.
Generated images are optimized to progressive JPEG before storage. If Cloudinary is configured, the worker uploads generated images there and stores the Cloudinary `secure_url` in the draft; otherwise it falls back to local `storage/image_jobs`.

Known limitations:

- Generated media is attached to local draft storage first. It is uploaded to Wildberries when the user runs the normal card push/media job.
- The worker must be running separately; the HTTP API does not generate images inline.
- If a worker dies mid-job, the Redis lock expires after `IMAGE_GENERATION_LOCK_TTL_SECONDS`.
