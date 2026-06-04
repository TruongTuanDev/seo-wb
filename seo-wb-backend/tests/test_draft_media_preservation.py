from app.api.routes.cards import _preserve_existing_media


def test_preserve_existing_media_by_vendor_code_on_draft_update():
    existing_payload = [
        {
            "subjectID": 180,
            "variants": [
                {
                    "vendorCode": "VC-001",
                    "media": {"cover": "/cards/media/5/cover.jpg", "local_files": [{"url": "/cards/media/5/cover.jpg"}]},
                }
            ],
        }
    ]
    next_payload = [
        {
            "subjectID": 180,
            "variants": [
                {
                    "vendorCode": "VC-001",
                    "title": "Updated title",
                }
            ],
        }
    ]

    result = _preserve_existing_media(existing_payload, next_payload)

    assert result[0]["variants"][0]["media"] == existing_payload[0]["variants"][0]["media"]
