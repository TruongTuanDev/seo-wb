import json
from app.db.session import SessionLocal
from app.models.card import CardDraft

def main():
    db = SessionLocal()
    try:
        draft = db.query(CardDraft).filter(CardDraft.id == 1).first()
        if not draft:
            print("Draft 1 not found!")
            return
        
        info = {
            "id": draft.id,
            "store_id": draft.store_id,
            "status": draft.status,
            "subject_id": draft.subject_id,
            "vendor_code": draft.vendor_code,
            "analysis": draft.analysis,
            "card_payload": draft.card_payload
        }
        
        with open("scratch_draft.json", "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2, ensure_ascii=False)
        print("Draft 1 details written to scratch_draft.json successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    main()
