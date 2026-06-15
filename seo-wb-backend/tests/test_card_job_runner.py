import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.card import CardUploadGroup
from app.services.card_job_runner import CardJobRunner


def _group(vendor_code: str = "VC-001") -> CardUploadGroup:
    return CardUploadGroup.model_validate(
        {
            "subjectID": 12,
            "variants": [
                {
                    "vendorCode": vendor_code,
                    "title": "Women's jeans",
                    "description": (
                        "Premium high-waist jeans with a comfortable fit and durable fabric for daily wear. "
                        "Designed for stable sizing, clean packaging, and marketplace-ready product content."
                    ),
                    "brand": "Test Brand",
                    "dimensions": {"length": 28, "width": 22, "height": 2, "weightBrutto": 0.4},
                    "characteristics": [{"id": 14177449, "value": ["blue"]}],
                    "sizes": [{"techSize": "25", "wbSize": "38", "skus": ["1234567890123"]}],
                }
            ],
        }
    )


class FakeFlow:
    def __init__(self, response):
        self._response = response

    async def get_card_errors(self):
        return self._response


class FakeLegacyVendorFlow(FakeFlow):
    async def get_cards_by_text(self, text_search, limit=100, with_photo=-1):
        if text_search.casefold() == "234/черный":
            return {"cards": [{"nmID": 1152698127, "vendorCode": "234/Черный"}]}
        return {"cards": []}


def test_format_job_error_preserves_app_error_details():
    exc = AppError(
        "wildberries_request_failed",
        "Wildberries API returned 400.",
        502,
        {"status_code": 400, "payload": {"errorText": "Invalid characteristic value"}},
    )

    message = CardJobRunner._format_job_error(exc)

    assert "wildberries_request_failed" in message
    assert "status_code" in message
    assert "Invalid characteristic value" in message


def test_vendor_code_aliases_include_russian_color_for_legacy_latin_suffix():
    variant = _group("234/CHERNYI").variants[0]
    variant.characteristics[0].value = ["черный"]

    aliases = CardJobRunner._vendor_code_aliases(variant)

    assert aliases == ["234/CHERNYI", "234/черный"]


@pytest.mark.anyio
async def test_wait_for_nm_ids_resolves_wb_normalized_russian_vendor_code(monkeypatch):
    variant_group = _group("234/CHERNYI")
    variant_group.variants[0].characteristics[0].value = ["черный"]
    runner = CardJobRunner(Settings(app_env="test", app_secret_key="test-secret-key"))

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr("app.services.card_job_runner.asyncio.sleep", no_sleep)
    nm_map = await runner._wait_for_nm_ids(FakeLegacyVendorFlow({"data": {"items": []}}), [variant_group])

    assert nm_map == {"234/CHERNYI": 1152698127}


@pytest.mark.anyio
async def test_raise_if_wb_errors_reads_vendor_code_error_map():
    runner = CardJobRunner(Settings(app_env="test", app_secret_key="test-secret-key"))

    with pytest.raises(RuntimeError) as exc_info:
        await runner._raise_if_wb_errors(
            FakeFlow(
                {
                    "data": {
                        "items": [
                            {
                                "object": "Джинсы",
                                "imtID": 123,
                                "errors": {"VC-001": ["Invalid value for required characteristic"]},
                            }
                        ]
                    }
                }
            ),
            [_group()],
        )

    message = str(exc_info.value)
    assert "VC-001" in message
    assert "Invalid value for required characteristic" in message
    assert "imtID=123" in message


@pytest.mark.anyio
async def test_raise_if_wb_errors_reads_item_level_errors():
    runner = CardJobRunner(Settings(app_env="test", app_secret_key="test-secret-key"))

    with pytest.raises(RuntimeError) as exc_info:
        await runner._raise_if_wb_errors(
            FakeFlow(
                {
                    "data": {
                        "errors": [
                            {
                                "vendorCode": "VC-001",
                                "subjectName": "Джинсы",
                                "errors": {"characteristics": ["Color is required"]},
                            }
                        ]
                    }
                }
            ),
            [_group()],
        )

    message = str(exc_info.value)
    assert "VC-001" in message
    assert "Color is required" in message
