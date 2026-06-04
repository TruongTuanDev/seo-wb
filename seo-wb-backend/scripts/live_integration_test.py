import asyncio
import json
import logging
import sys
from pathlib import Path

# Configure logging to show all details beautifully
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("live_integration_test")

# Monkeypatch WbBaseClient to auto-throttle/sleep instead of throwing client-side rate limit errors
from app.services.wb_base_client import WbBaseClient

original_request = WbBaseClient.request
async def throttled_request(self, *args, **kwargs):
    # We sleep 0.75 seconds to ensure we never violate the 0.6 seconds client-side min_interval_seconds limit
    await asyncio.sleep(0.75)
    return await original_request(self, *args, **kwargs)

WbBaseClient.request = throttled_request
logger.info("Successfully monkeypatched WbBaseClient to add 0.75s request throttling.")

from app.core.config import get_settings
from app.core.security import encrypt_secret
from app.db.session import SessionLocal
from app.models.store import Store
from app.models.user import User
from app.models.card import CardDraft
from app.schemas.card import ProductInput, CardUploadGroup
from app.services.card_flow import CardFlowService

# The user-provided JWT Wildberries API token
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
    logger.info("Starting live integration test with 0.75s throttling...")
    settings = get_settings()

    # 1. Open Database Session
    db = SessionLocal()
    try:
        # 2. Get the target user and store
        user = db.query(User).filter(User.id == 1).first()
        store = db.query(Store).filter(Store.id == 2).first()

        if not user or not store:
            logger.error("User ID 1 or Store ID 2 not found in database!")
            return

        logger.info(f"Using User: {user.email} (ID: {user.id})")
        logger.info(f"Target Store: {store.name} (ID: {store.id})")

        # 3. Update the store's Wildberries API token
        logger.info("Encrypting and updating Store Wildberries API token...")
        encrypted_token = encrypt_secret(settings, USER_WB_API_KEY)
        store.wb_api_key_encrypted = encrypted_token
        db.commit()
        logger.info("Store API key updated successfully in database!")

        # Refresh from db to be absolutely sure
        db.refresh(store)

        # 4. Load the product image
        if not IMAGE_PATH.exists():
            logger.error(f"Image not found at path: {IMAGE_PATH}")
            return
        
        logger.info(f"Loading image from {IMAGE_PATH}...")
        image_bytes = IMAGE_PATH.read_bytes()
        logger.info(f"Loaded {len(image_bytes)} bytes of image data.")

        # 5. Build user input
        product_input = ProductInput(
            category="Костюм", 
            brand="Nike",
            vendor_code="NK-BLUEGREY-SET",
            color="Темно-серый", 
            gender="Мужской",
            sizes=["S-42", "M-44", "L-46"],
            dimensions={
                "length": 30,
                "width": 25,
                "height": 6,
                "weightBrutto": 0.6
            },
            note="Спортивный мужской костюм: оверсайз футболка и шорты.",
            attributes={}
        )

        logger.info("Creating CardFlowService instance...")
        flow = CardFlowService(settings, db, user, store)

        # 6. Execute AI analysis and generate draft card
        logger.info("Running AI analysis and draft generation...")
        draft = await flow.generate_draft([image_bytes], product_input)
        logger.info(f"Draft generated successfully! Draft ID: {draft.id}")
        logger.info(f"Analysis results:\n{json.dumps(draft.analysis, indent=2, ensure_ascii=False)}")
        logger.info(f"Generated Card Payload:\n{json.dumps(draft.card_payload, indent=2, ensure_ascii=False)}")

        # 7. Push draft with dry_run = True for sandbox validation
        logger.info("Performing dry-run push (validation) against Wildberries API...")
        groups = [CardUploadGroup.model_validate(group) for group in draft.card_payload]
        
        try:
            dry_run_response = await flow.push_new_cards(groups, dry_run=True)
            logger.info("Dry-run validation successful! No exceptions raised.")
            logger.info(f"Dry-run response: {dry_run_response}")
        except Exception as e:
            logger.exception("Dry-run validation raised an error:")
            return

        # 8. Perform real live push to Wildberries API
        logger.info("Performing real live push to Wildberries API...")
        try:
            wb_response = await flow.push_new_cards(groups, dry_run=False)
            logger.info(f"Live push completed successfully! Wildberries API Response:\n{json.dumps(wb_response, indent=2, ensure_ascii=False)}")
            
            # Save the response in the draft database
            draft.status = "pushed"
            draft.wb_response = wb_response
            db.commit()
            logger.info("Database updated with pushed status and WB response!")
        except Exception as e:
            logger.exception("Live push to Wildberries API failed:")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
