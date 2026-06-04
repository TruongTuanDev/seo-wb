# Frontend Contract for Antigravity

Base URL in local development: `http://localhost:8000/api/v1`

Use `Authorization: Bearer <access_token>` for every endpoint except auth and health.

## Auth

### Register

`POST /auth/register`

```json
{
  "name": "Seller Name",
  "email": "seller@example.com",
  "password": "password123",
  "confirm_password": "password123"
}
```

### Login

`POST /auth/login`

```json
{
  "email": "seller@example.com",
  "password": "password123"
}
```

Both return:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "name": "Seller Name",
    "email": "seller@example.com"
  }
}
```

## Stores

### Create Store

`POST /stores`

```json
{
  "name": "My WB Store",
  "wb_api_key": "wildberries-content-api-token"
}
```

The API key is encrypted at rest. The frontend never receives it back.

### List Stores

`GET /stores`

## Wildberries Metadata

### Subjects

`GET /wb/subjects?store_id=1&parent_id=1&q=джинсы`

For clothes, `parent_id=1`.

### Subject Characteristics

`GET /wb/subjects/{subject_id}/charcs?store_id=1`

Frontend should use this to render required/popular fields and validate AI output.

## Generate Card Draft

`POST /cards/generate`

Content-Type: `multipart/form-data`

Fields:

- `store_id`: number
- `product_input_json`: stringified JSON
- `images`: one or more files

`product_input_json`:

```json
{
  "category": "Джинсы",
  "subject_id": 180,
  "brand": "My Brand",
  "vendor_code": "JEANS-001",
  "color": "синий",
  "gender": "Женский",
  "sizes": ["S", "M", "L"],
  "note": "широкие джинсы, высокая посадка",
  "attributes": {}
}
```

Response:

```json
{
  "draft_id": 1,
  "analysis": {
    "category": "Джинсы",
    "product_name": "...",
    "material": "...",
    "color": "...",
    "gender": "...",
    "season": "...",
    "fit_type": "...",
    "features": [],
    "attributes": {},
    "confidence": 0.9,
    "warnings": [],
    "source_image_count": 2
  },
  "card_payload": [
    {
      "subjectID": 180,
      "variants": [
        {
          "vendorCode": "JEANS-001",
          "title": "...",
          "description": "...",
          "brand": "My Brand",
          "dimensions": {
            "length": 30,
            "width": 25,
            "height": 5,
            "weightBrutto": 0.5
          },
          "characteristics": [
            {
              "id": 14177449,
              "value": ["синий"]
            }
          ],
          "sizes": [
            {
              "techSize": "S",
              "skus": []
            }
          ]
        }
      ]
    }
  ],
  "warnings": []
}
```

Frontend should render all fields editable before push:

- `vendorCode`
- `title`
- `description`
- `brand`
- `dimensions`
- `characteristics`
- `sizes`

## Save Edited Draft

`PUT /cards/drafts/{draft_id}`

Body:

```json
{
  "card_payload": []
}
```

Use the same payload structure returned by generate.

## Push New Card to Wildberries

`POST /cards/drafts/{draft_id}/push`

```json
{
  "dry_run": true
}
```

Set `dry_run=false` only after the user confirms.

Notes:

- If `sizes[].skus` are empty, backend generates SKUs from `/content/v2/barcodes` before pushing.
- WB card creation is async. A `200` response does not mean the card is immediately visible.
- Use `GET /wb/card-errors?store_id=1` to inspect async creation errors.

## Merge Card Into Existing imtID

`POST /cards/stores/{store_id}/push-merge`

```json
{
  "imtID": 987654321,
  "cardsToAdd": [],
  "dry_run": true
}
```

Use only when adding variants to an existing WB card group.

## Upload Media After nmID Exists

Wildberries card creation does not accept images in `/content/v2/cards/upload`.

After WB creates/returns an `nmID`, upload media:

### Upload via Direct Links

`POST /cards/{nm_id}/media?store_id=1`

```json
{
  "links": [
    "https://cdn.example.com/product-front.jpg",
    "https://cdn.example.com/product-back.jpg"
  ]
}
```

### Upload File

`POST /cards/{nm_id}/media-file`

multipart fields:

- `store_id`
- `photo_number`
- `file`

## Recommended UI Flow

1. Login/register.
2. Create or select store.
3. In Create Card page, upload 2+ images and enter prompt/product data.
4. Call `POST /cards/generate`.
5. Show Gemini analysis + editable WB card fields.
6. User edits dimensions, size, brand, vendor code, characteristics.
7. Call `POST /cards/drafts/{draft_id}/push` with `dry_run=true`.
8. If payload looks correct, call again with `dry_run=false`.
9. Poll/check `/wb/card-errors`.
10. Once `nmID` is known, upload media.

## Extended WB Metadata and Merge APIs

Use these additional endpoints for a complete frontend flow:

- `GET /wb/parent-categories?store_id=1`
- `GET /wb/directories/colors?store_id=1`
- `GET /wb/directories/kinds?store_id=1`
- `GET /wb/directories/countries?store_id=1`
- `GET /wb/directories/seasons?store_id=1`
- `GET /wb/directories/vat?store_id=1`
- `GET /wb/subjects/{subject_id}/tnved?store_id=1`
- `POST /wb/tnved/suggest?store_id=1`
- `POST /wb/payload/enrich-tnved?store_id=1`
- `GET /wb/subjects/{subject_id}/brands?store_id=1`
- `GET /wb/card-limits?store_id=1`
- `POST /wb/cards/list?store_id=1`
- `POST /cards/stores/{store_id}/move-nm`

TNVED suggestion request:

```json
{
  "subjectID": 11,
  "search": null
}
```

Cards list request:

```json
{
  "textSearch": "25101/DEN",
  "withPhoto": -1,
  "limit": 100
}
```

Move or merge existing `nmID` cards:

```json
{
  "targetIMT": 1630843654,
  "nmIDs": [978043271],
  "dry_run": false
}
```

WB `/content/v2/cards/upload/add` has a strict base limiter of 1 request per 2 hours. If it returns `429`, create the product as a new card first, poll until `nmID` exists, then call `/cards/stores/{store_id}/move-nm` to merge it into the target `imtID`.

Full frontend build prompt: [ANTIGRAVITY_FRONTEND_PROMPT.md](./ANTIGRAVITY_FRONTEND_PROMPT.md)
