from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine_kwargs = {"connect_args": connect_args, "pool_pre_ping": True}
if not settings.database_url.startswith("sqlite"):
    engine_kwargs.update(
        {
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_recycle": settings.db_pool_recycle_seconds,
        }
    )
engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    if not settings.db_auto_create:
        return

    from app.models.admin import AdminAiSettings, AdminAuditLog, GeneratedImageJob, ModelTemplate, UsageRecord
    from app.models.billing import CreditTransaction, PaymentTransaction, PlatformAuditLog, SubscriptionPlan, UserSubscription
    from app.models.card import CardDraft, CardJob
    from app.models.finance import (
        ApiDiagnosticLog,
        ExternalCost,
        FinanceAnalysisSnapshot,
        ProductFinanceSetting,
        SellerFinanceAutomationState,
        SellerFinanceSettings,
        WbFinanceReportRow,
        WbFinanceSyncState,
    )
    from app.models.seller import Seller
    from app.models.shop_model import ShopModel
    from app.models.store import Store
    from app.models.user import User
    from app.models.wb_product import WbProduct, WbProductSyncState

    _ = (
        AdminAiSettings,
        AdminAuditLog,
        ApiDiagnosticLog,
        CardDraft,
        CardJob,
        CreditTransaction,
        ExternalCost,
        FinanceAnalysisSnapshot,
        GeneratedImageJob,
        ModelTemplate,
        PaymentTransaction,
        PlatformAuditLog,
        ProductFinanceSetting,
        SellerFinanceAutomationState,
        Seller,
        ShopModel,
        SellerFinanceSettings,
        Store,
        SubscriptionPlan,
        User,
        UsageRecord,
        UserSubscription,
        WbFinanceReportRow,
        WbFinanceSyncState,
        WbProduct,
        WbProductSyncState,
    )
    Base.metadata.create_all(bind=engine)
