from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.seller import Seller
from app.models.store import Store
from app.models.user import User
from app.models.wb_product import WbProduct, WbProductSyncState
from app.services.wb_product_sync_service import WbProductSyncService


class DummyContentClient:
    def __init__(self):
        self.payloads = []
        self.calls = 0

    async def get_cards_list(self, payload):
        self.payloads.append(payload)
        self.calls += 1
        if self.calls == 1:
            return {
                "cards": [
                    {
                        "nmID": 10,
                        "imtID": 100,
                        "vendorCode": "ART-10",
                        "title": "Product A",
                        "sizes": [{"skus": ["SKU-10"]}],
                        "characteristics": [],
                        "updatedAt": "2026-05-18T08:00:00Z",
                    }
                ],
                "cursor": {"updatedAt": "2026-05-18T08:00:00Z", "nmID": 10, "total": 1},
            }
        return {"cards": [], "cursor": {"updatedAt": "2026-05-18T08:00:00Z", "nmID": 10, "total": 0}}


@pytest.mark.anyio
async def test_product_sync_uses_ascending_cursor_and_upserts(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    _ = (User, Store, Seller, WbProduct, WbProductSyncState)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        user = User(name="Seller", email="seller@example.com", password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        store = Store(user_id=user.id, name="Demo Store", wb_api_key_encrypted="encrypted")
        db.add(store)
        db.commit()
        db.refresh(store)
        seller = Seller(store_id=store.id, name="Seller Name")
        db.add(seller)
        db.commit()
        db.refresh(seller)

        state = WbProductSyncState(seller_id=seller.id, sync_type="active_cards", cursor_nm_id=9)
        db.add(state)
        db.commit()

        client = DummyContentClient()
        service = WbProductSyncService(db, seller, client)
        result = await service.sync()

        assert result["status"] == "completed"
        assert client.payloads[0]["settings"]["sort"]["ascending"] is True
        assert client.payloads[0]["settings"]["cursor"]["nmID"] == 9
        product = db.query(WbProduct).filter(WbProduct.seller_id == seller.id, WbProduct.nm_id == 10).one()
        assert product.vendor_code == "ART-10"
        assert product.skus == ["SKU-10"]

        client2 = DummyContentClient()
        await WbProductSyncService(db, seller, client2).sync()
        assert db.query(WbProduct).filter(WbProduct.seller_id == seller.id, WbProduct.nm_id == 10).count() == 1

