from sqlalchemy.orm import Session

from app.models.seller import Seller
from app.models.store import Store


def ensure_seller_for_store(db: Session, store: Store) -> Seller:
    seller = db.query(Seller).filter(Seller.store_id == store.id).one_or_none()
    if seller:
        return seller
    seller = Seller(store_id=store.id, name=store.name)
    db.add(seller)
    db.commit()
    db.refresh(seller)
    return seller


def update_seller_from_wb(db: Session, seller: Seller, payload: dict) -> Seller:
    seller.external_sid = str(payload.get("sid") or payload.get("externalSid") or seller.external_sid or "") or None
    seller.name = payload.get("name") or seller.name
    seller.trade_mark = payload.get("tradeMark") or payload.get("trade_mark") or seller.trade_mark
    seller.tin = str(payload.get("tin") or seller.tin or "") or None
    db.commit()
    db.refresh(seller)
    return seller
