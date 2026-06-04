import asyncio
import json
import logging
import sys
import hashlib
import time
from pathlib import Path
import httpx
import copy

# Configure logging to show all details beautifully
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("live_job_e2e_test")

from app.core.config import get_settings
from app.core.security import encrypt_secret, create_access_token
from app.db.session import SessionLocal
from app.models.store import Store
from app.models.user import User
from app.models.card import CardDraft

USER_WB_API_KEY = (
    "eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjUwOTA0djEiLCJ0eXAiOiJKV1QifQ."
    "eyJhY2MiOjEsImVudCI6MSwiZXhwIjoxNzc5OTg4OTQ5LCJpZCI6IjAxOWFjM2Mz"
    "LTUzN2MtN2M3NS1iOGUxLTE2MTVhNTEyZjA0MiIsImlpZCI6MzAxMDU1MDI1LCJv"
    "aWQiOjI1MDAzMzQxMCwicyI6MTYxMjYsInNpZCI6ImJlZDQxMzgwLTQ0MDEtNDI1"
    "Zi05ZDA0LTMxOTJkMWUyNmQyOCIsInQiOmZhbHNlLCJ1aWQiOjMwMTA1NTAyNX0."
    "GCYGGl4imVfZQ52viy4OyV1tm62vqaoZZ86uHtLuMs1MnaKxdzF4m5WE2bTNaPtq"
    "YCSoFoisY3UEhYxFnRabbg"
)

IMAGE_PATH = Path(r"C:\Users\nanht\.gemini\antigravity\brain\11f36049-ac49-4196-8570-a09b53c149b9\media__1779301638859.jpg")

async def main():
    logger.info("Initializing E2E Live Integration Test...")
    settings = get_settings()

    card_payload = None
    user_id = None
    store_id = None

    # 1. Update WB API Key in database for Store ID 2 and read draft attributes
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == 1).first()
        store = db.query(Store).filter(Store.id == 2).first()
        draft = db.query(CardDraft).filter(CardDraft.id == 1).first()

        if not user or not store or not draft:
            logger.error("Required user/store/draft not found in database!")
            return

        user_id = user.id
        store_id = store.id
        logger.info(f"Using User: {user.email} (ID: {user_id})")
        logger.info(f"Target Store: {store.name} (ID: {store_id})")

        logger.info("Encrypting and updating Store Wildberries API token...")
        encrypted_token = encrypt_secret(settings, USER_WB_API_KEY)
        store.wb_api_key_encrypted = encrypted_token
        db.commit()
        logger.info("Store API key updated successfully in database!")
        
        # Access and deep copy payload while session is active
        card_payload = copy.deepcopy(draft.card_payload)
    finally:
        db.close()

    # 2. Prepare Unique Vendor Code
    timestamp = int(time.time())
    unique_vendor_code = f"NK-SET-E2E-{timestamp}"
    logger.info(f"Using unique E2E Vendor Code for test: {unique_vendor_code}")

    if card_payload and "variants" in card_payload[0] and card_payload[0]["variants"]:
        card_payload[0]["variants"][0]["vendorCode"] = unique_vendor_code
    
    # 3. Generate Auth JWT Token with Fingerprint matching custom User-Agent
    user_agent = "E2ELiveIntegrationTestClient/1.0"
    fp = hashlib.sha256(f"{settings.app_secret_key}:{user_agent}".encode("utf-8")).hexdigest()
    
    # Create the access token using user ID 1
    token = create_access_token(settings, str(user_id), extra={"fp": fp})
    logger.info("Generated valid Bearer JWT access token for User ID 1 with fingerprint binding.")

    # 4. Prepare multipart/form-data for the jobs endpoint
    if not IMAGE_PATH.exists():
        logger.error(f"Image not found at: {IMAGE_PATH}")
        return

    media_manifest = {
        "items": [
            {
                "vendorCode": unique_vendor_code,
                "photoNumber": 1,
                "fileName": f"{unique_vendor_code}.jpg"
            }
        ]
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": user_agent
    }

    files = {
        "files": (f"{unique_vendor_code}.jpg", IMAGE_PATH.read_bytes(), "image/jpeg")
    }

    data = {
        "store_id": str(store_id),
        "mode": "create_new",
        "card_payload_json": json.dumps(card_payload),
        "media_manifest_json": json.dumps(media_manifest),
        "draft_id": "1"
    }

    # 5. Call API to enqueue job
    api_url = "http://127.0.0.1:8000/api/v1/cards/jobs"
    logger.info(f"POSTing job to FastAPI endpoint: {api_url}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(api_url, headers=headers, data=data, files=files)
        if response.status_code != 200:
            logger.error(f"Failed to enqueue job! HTTP {response.status_code}: {response.text}")
            return
        
        job_info = response.json()
        job_id = job_info.get("id")
        logger.info(f"Successfully enqueued job! Job ID: {job_id}")
        logger.info(f"Initial Job Info:\n{json.dumps(job_info, indent=2, ensure_ascii=False)}")

        # 6. Poll Job Status
        poll_url = f"http://127.0.0.1:8000/api/v1/cards/jobs/{job_id}"
        logger.info(f"Starting status polling loop for Job ID {job_id} at {poll_url}")
        
        while True:
            poll_resp = await client.get(poll_url, headers=headers)
            if poll_resp.status_code != 200:
                logger.error(f"Failed to poll job status! HTTP {poll_resp.status_code}: {poll_resp.text}")
                await asyncio.sleep(5.0)
                continue
                
            job_status = poll_resp.json()
            status = job_status.get("status")
            step = job_status.get("step")
            err_msg = job_status.get("error")
            
            logger.info(f"Job #{job_id} Status: {status.upper()} | Step: {step.upper()}")
            
            if status == "completed":
                logger.info("=" * 60)
                logger.info("SUCCESS! E2E Job completed successfully!")
                logger.info(f"Final Job Results:\n{json.dumps(job_status.get('result'), indent=2, ensure_ascii=False)}")
                logger.info("=" * 60)
                break
            elif status == "failed":
                logger.error("=" * 60)
                logger.error(f"FAILURE! Job failed at step: {step.upper()}")
                logger.error(f"Error Message: {err_msg}")
                logger.error("=" * 60)
                break
                
            await asyncio.sleep(3.0)

if __name__ == "__main__":
    asyncio.run(main())
