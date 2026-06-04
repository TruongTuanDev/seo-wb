import sys
from sqlalchemy import text
from app.db.session import SessionLocal
from app.models.user import User
from app.models.store import Store
from app.models.card import CardDraft, CardJob

def main():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print("--- USERS ---")
        for u in users:
            print(f"ID: {u.id}, Email: {u.email}")
            
        stores = db.query(Store).all()
        print("\n--- STORES ---")
        for s in stores:
            print(f"ID: {s.id}, Name: {s.name}, User ID: {s.user_id}")
            
        drafts = db.query(CardDraft).all()
        print("\n--- DRAFTS ---")
        for d in drafts:
            print(f"ID: {d.id}, Store ID: {d.store_id}, Status: {d.status}, Subject ID: {d.subject_id}, Vendor Code: {d.vendor_code}")
            
        jobs = db.query(CardJob).all()
        print("\n--- JOBS ---")
        for j in jobs:
            print(f"ID: {j.id}, Store ID: {j.store_id}, Status: {j.status}, Step: {j.step}, Draft ID: {j.draft_id}, Error: {j.error}")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
