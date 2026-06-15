from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import Base
from app.models.shop_model import ShopModel
from app.models.store import Store
from app.models.user import User
from app.services.shop_model_service import get_owned_shop_model, resolve_model_reference


def test_shop_model_is_isolated_by_store(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        user = User(name="Seller", email="seller@example.com", password_hash="hash")
        db.add(user)
        db.flush()
        first_store = Store(user_id=user.id, name="First", wb_api_key_encrypted="secret")
        second_store = Store(user_id=user.id, name="Second", wb_api_key_encrypted="secret")
        db.add_all([first_store, second_store])
        db.flush()

        image_path = Path("storage/shop_models") / str(first_store.id) / "model-a" / "reference.jpg"
        image_path.parent.mkdir(parents=True)
        image_path.write_bytes(b"shop-model")
        model = ShopModel(
            id="model-a",
            store_id=first_store.id,
            name="Anna",
            gender="Female",
            body_type="Regular",
            reference_image_url=f"/storage/shop_models/{first_store.id}/model-a/reference.jpg",
            thumbnail_url=f"/storage/shop_models/{first_store.id}/model-a/reference.jpg",
            poses={},
        )
        db.add(model)
        db.commit()

        assert get_owned_shop_model(db, first_store.id, model.id).id == model.id
        with pytest.raises(AppError) as denied:
            get_owned_shop_model(db, second_store.id, model.id)
        assert denied.value.code == "shop_model_not_found"

        resolved_path, _, gender, body_type, source = resolve_model_reference(
            db,
            store_id=first_store.id,
            model_id=model.id,
        )
        assert resolved_path.read_bytes() == b"shop-model"
        assert (gender, body_type, source) == ("Female", "Regular", "shop")

        with pytest.raises(AppError) as cross_shop:
            resolve_model_reference(db, store_id=second_store.id, model_id=model.id)
        assert cross_shop.value.code == "model_not_available"
