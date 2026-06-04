from datetime import UTC, date, datetime
from decimal import Decimal
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.session import Base
from app.models.finance import (
    ExternalCost,
    FinanceAnalysisSnapshot,
    ProductFinanceSetting,
    SellerFinanceAutomationState,
    SellerFinanceSettings,
    WbFinanceReportRow,
    WbFinanceSyncState,
    WbFinancialDailySummary,
)
from app.models.seller import Seller
from app.models.store import Store
from app.models.user import User
from app.models.wb_product import WbProduct, WbProductSyncState
from app.services.finance_service import FinanceAggregationService, FinanceSettingsService, FinanceSyncService, FinanceSystemStatusService
from app.services.wb_base_client import CooldownState, WbNoData, WbRateLimitError
from app.services import wb_base_client


class DummyFinanceClient:
    def __init__(self):
        self.calls = 0

    async def get_sales_reports_detailed_by_period(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return [
                {
                    "rrdId": 1001,
                    "reportId": 55,
                    "dateFrom": "2026-03-01T00:00:00+00:00",
                    "dateTo": "2026-03-31T23:59:59+00:00",
                    "createDate": "2026-04-01",
                    "currency": "RUB",
                    "reportType": 1,
                    "nmId": 987654,
                    "vendorCode": "SKU-RED-1",
                    "title": "Demo Product",
                    "subjectName": "Джинсы",
                    "techSize": "M",
                    "sku": "BC-001",
                    "docTypeName": "Продажа",
                    "quantity": 2,
                    "retailPrice": "1000.00",
                    "retailAmount": "2000.00",
                    "retailPriceWithDisc": "1800.00",
                    "salePercent": "10.0",
                    "commissionPercent": "20.0",
                    "sellerOperName": "Продажа",
                    "saleDt": "2026-03-10T10:00:00+00:00",
                    "rrDate": "2026-03-10",
                    "deliveryAmount": 0,
                    "returnAmount": 0,
                    "deliveryService": "50.00",
                    "ppvzSalesCommission": "200.00",
                    "forPay": "1500.00",
                    "acquiringFee": "20.00",
                    "acquiringPercent": "1.0",
                    "penalty": "0",
                    "additionalPayment": "0",
                    "rebillLogisticCost": "0",
                    "paidStorage": "0",
                    "deduction": "0",
                    "paidAcceptance": "0",
                    "cashbackAmount": "0",
                    "cashbackDiscount": "0",
                    "cashbackCommissionChange": "0",
                    "agencyVat": "0",
                }
            ]
        raise WbNoData("wildberries_no_data", "Wildberries returned no data.", 204)


class DummyFinanceClientMultiPage:
    def __init__(self):
        self.calls = 0
        self.args = []

    async def get_sales_reports_detailed_by_period(self, **kwargs):
        self.args.append(kwargs)
        self.calls += 1
        if self.calls == 1:
            return [
                {
                    "rrdId": 10,
                    "dateFrom": "2026-03-01T00:00:00+00:00",
                    "dateTo": "2026-03-31T23:59:59+00:00",
                    "nmId": 987654,
                    "vendorCode": "SKU-RED-1",
                    "sku": "BC-001",
                    "quantity": 1,
                    "retailAmount": "100.00",
                    "forPay": "80.00",
                    "rrDate": "2026-03-10",
                }
            ]
        if self.calls == 2:
            return [
                {
                    "rrdId": 11,
                    "dateFrom": "2026-03-01T00:00:00+00:00",
                    "dateTo": "2026-03-31T23:59:59+00:00",
                    "nmId": 987654,
                    "vendorCode": "SKU-RED-1",
                    "sku": "BC-001",
                    "quantity": 1,
                    "retailAmount": "150.00",
                    "forPay": "120.00",
                    "rrDate": "2026-03-11",
                }
            ]
        raise WbNoData("wildberries_no_data", "Wildberries returned no data.", 204)


class DummyFinanceClientRateLimited:
    async def get_sales_reports_detailed_by_period(self, **kwargs):
        raise WbRateLimitError("wildberries_rate_limited", "Wildberries API rate limit reached.", 429, {"retry_after_seconds": 60})


@pytest.mark.anyio
async def test_finance_sync_and_aggregation_workflow(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    _ = (
        User,
        Store,
        Seller,
        WbProduct,
        WbProductSyncState,
        SellerFinanceSettings,
        ProductFinanceSetting,
        SellerFinanceAutomationState,
        ExternalCost,
        WbFinanceReportRow,
        WbFinanceSyncState,
        FinanceAnalysisSnapshot,
    )
    Base.metadata.create_all(bind=engine)
    settings = Settings(app_env="test", app_secret_key="test-secret-key", database_url=f"sqlite:///{tmp_path / 'test.db'}")

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
        product = WbProduct(
            seller_id=seller.id,
            nm_id=987654,
            vendor_code="SKU-RED-1",
            title="Demo Product",
            skus=["BC-001"],
            characteristics=[],
            sizes=[],
            raw_data={},
        )
        db.add(product)
        db.commit()
        db.refresh(product)

        settings_service = FinanceSettingsService(db, seller)
        settings_service.update_seller_settings({"default_tax_mode": "USN_PROFIT", "default_tax_rate": "0.10"})
        settings_service.upsert_product_setting(
            product.id,
            {
                "cost_price": "400.00",
                "packaging_cost": "20.00",
                "labeling_cost": "10.00",
                "shipping_to_warehouse_cost": "30.00",
                "other_unit_cost": "0",
                "effective_from": date(2026, 3, 1),
            },
        )
        settings_service.create_external_cost(
            {
                "cost_date": date(2026, 3, 15),
                "cost_type": "ads",
                "amount": "100.00",
                "allocation_method": "DIRECT_PRODUCT",
                "product_id": product.id,
            }
        )

        sync_service = FinanceSyncService(db, settings, seller, DummyFinanceClient())
        result = await sync_service.sync(date_from=date(2026, 3, 1), date_to=date(2026, 3, 31), period="daily")
        assert result["status"] == "completed"
        assert db.query(WbFinanceReportRow).count() == 1

        db.add(WbFinancialDailySummary(
            seller_id=seller.id,
            summary_date=date(2026, 3, 10),
            gross_revenue=Decimal("2000.0000"),
            for_pay=Decimal("1500.0000"),
            wb_costs=Decimal("270.0000"),
            cogs=Decimal("920.0000"),
            tax_amount=Decimal("48.0000"),
            profit_before_tax=Decimal("580.0000"),
            profit_after_tax=Decimal("532.0000"),
            raw_row_count=1
        ))
        db.commit()

        summary = FinanceAggregationService(db, seller).summary(date(2026, 3, 1), date(2026, 3, 31))
        assert summary["grossRevenue"] == "2000.0000"
        assert summary["forPay"] == "1500.0000"
        assert summary["profitBeforeTax"] == "480.0000"
        assert summary["profitAfterTax"] == "432.0000"
        assert summary["costCompletenessPercent"] == "100.0000"

        products = FinanceAggregationService(db, seller).product_breakdown(date(2026, 3, 1), date(2026, 3, 31))
        assert products[0]["vendorCode"] == "SKU-RED-1"
        assert products[0]["cogs"] == "920.0000"
        assert products[0]["externalAllocatedCosts"] == "100.0000"


@pytest.mark.anyio
async def test_finance_sync_multi_page_resume_and_rate_limited_status(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    _ = (
        User,
        Store,
        Seller,
        WbProduct,
        WbProductSyncState,
        SellerFinanceSettings,
        ProductFinanceSetting,
        SellerFinanceAutomationState,
        ExternalCost,
        WbFinanceReportRow,
        WbFinanceSyncState,
        FinanceAnalysisSnapshot,
    )
    Base.metadata.create_all(bind=engine)
    settings = Settings(app_env="test", app_secret_key="test-secret-key", database_url=f"sqlite:///{tmp_path / 'test.db'}")

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
        product = WbProduct(seller_id=seller.id, nm_id=987654, vendor_code="SKU-RED-1", title="Demo Product", skus=["BC-001"], characteristics=[], sizes=[], raw_data={})
        db.add(product)
        db.commit()
        db.refresh(product)

        client = DummyFinanceClientMultiPage()
        sync_service = FinanceSyncService(db, settings, seller, client)
        result = await sync_service.sync(date_from=date(2026, 3, 1), date_to=date(2026, 3, 31), period="daily")
        assert result["status"] == "completed"
        assert db.query(WbFinanceReportRow).count() == 2
        assert client.args[0]["rrd_id"] == 0
        assert client.args[1]["rrd_id"] == 10

        result_again = await sync_service.sync(date_from=date(2026, 3, 1), date_to=date(2026, 3, 31), period="daily")
        assert result_again["status"] == "completed"
        assert db.query(WbFinanceReportRow).count() == 2

        limited_service = FinanceSyncService(db, settings, seller, DummyFinanceClientRateLimited())
        with pytest.raises(WbRateLimitError):
            await limited_service.sync(date_from=date(2026, 4, 1), date_to=date(2026, 4, 2), period="daily")
        state = db.query(WbFinanceSyncState).filter(WbFinanceSyncState.date_from == date(2026, 4, 1)).one()
        assert state.status == "rate_limited"
        assert "retry_after_seconds=60" in (state.last_error or "")


@pytest.mark.anyio
async def test_finance_system_status_reads_local_state_only(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    _ = (
        User,
        Store,
        Seller,
        WbProduct,
        WbProductSyncState,
        SellerFinanceSettings,
        ProductFinanceSetting,
        SellerFinanceAutomationState,
        ExternalCost,
        WbFinanceReportRow,
        WbFinanceSyncState,
        FinanceAnalysisSnapshot,
    )
    Base.metadata.create_all(bind=engine)
    settings = Settings(app_env="test", app_secret_key="test-secret-key", database_url=f"sqlite:///{tmp_path / 'test.db'}")
    wb_base_client._server_cooldowns.clear()

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
        product = WbProduct(seller_id=seller.id, nm_id=987654, vendor_code="SKU-RED-1", title="Demo Product", skus=["BC-001"], characteristics=[], sizes=[], raw_data={})
        db.add(product)
        db.commit()
        db.refresh(product)
        db.add(WbProductSyncState(seller_id=seller.id, sync_type="active_cards", status="completed", finished_at=datetime(2026, 5, 18, 8, 0, tzinfo=UTC)))
        db.add(WbFinanceSyncState(seller_id=seller.id, date_from=date(2026, 3, 1), date_to=date(2026, 3, 31), period="daily", status="failed", last_error="rate_limited retry_after_seconds=60", finished_at=datetime(2026, 5, 18, 9, 0, tzinfo=UTC)))
        db.add(
            SellerFinanceAutomationState(
                seller_id=seller.id,
                timezone="Europe/Moscow",
                bootstrap_status="completed",
                bootstrap_range_from=date(2026, 4, 18),
                bootstrap_range_to=date(2026, 5, 17),
                bootstrap_finished_at=datetime(2026, 5, 18, 7, 30, tzinfo=UTC),
                last_successful_daily_sync_date=date(2026, 5, 17),
                last_daily_status="completed",
            )
        )
        db.add(WbFinanceReportRow(seller_id=seller.id, rrd_id=100, raw_data={}, product_id=None))
        db.commit()

        wb_base_client._server_cooldowns[f"{seller.id}:finance:https://finance-api.wildberries.ru:GET:/api/v1/account/balance"] = CooldownState(
            seller_key=str(seller.id),
            category="finance",
            host="finance-api.wildberries.ru",
            method="GET",
            endpoint="/api/v1/account/balance",
            active_until_monotonic=time.monotonic() + 120.0,
            retry_after_seconds=120.0,
        )
        status = await FinanceSystemStatusService(db, settings, seller).build()
        assert status["financeApi"]["inCooldown"] is True
        assert (status["lastSuccessfulProductSyncAt"] or "").startswith("2026-05-18T08:00:00")
        assert (status["lastFailedSyncAt"] or "").startswith("2026-05-18T09:00:00")
        assert status["hasProductsMissingFinanceSettings"] is True
        assert status["hasUnmappedFinanceRows"] is True
        assert status["automationTimezone"] == "Europe/Moscow"
        assert status["bootstrapStatus"] == "completed"
        assert status["lastSuccessfulDailySyncDate"] == "2026-05-17"
        assert status["nextScheduledRunAt"] is not None
