# Repository Agent Instructions

## Mandatory product-card context

Before changing any code related to Wildberries product-card generation, SEO,
subjects, characteristics, variants, titles, descriptions, or vendor codes,
read:

- `docs/WB_SEO_SOURCE_OF_TRUTH.md`

That document is the product and engineering source of truth for this
repository. Its `MUST` and `MUST NOT` rules override older prompts, comments,
tests, admin defaults, and generic marketplace SEO assumptions.

## Scope covered by the source of truth

The requirement applies especially to:

- `seo-wb-backend/app/services/card_flow.py`
- `seo-wb-backend/app/services/card_generator.py`
- `seo-wb-backend/app/services/seo_keyword_planner.py`
- `seo-wb-backend/app/services/product_copy_policy.py`
- `seo-wb-backend/app/services/seo_content_validator.py`
- `seo-wb-backend/app/services/subject_rule_registry.py`
- `seo-wb-backend/app/services/title_template_registry.py`
- `seo-wb-backend/app/services/card_payload_enricher.py`
- `seo-wb-backend/app/services/critical_attribute_validator.py`
- `seo-wb-backend/app/services/semantic_consistency_validator.py`
- card-generation routes and frontend card-creation UI

## Change discipline

- Treat WB subject characteristics returned by the live Content API as the
  authority for allowed and required fields.
- Do not hardcode a generic fashion rule when the behavior belongs to a WB
  subject.
- Keep unknown subjects backward compatible through a conservative family
  fallback.
- Add or update tests whenever a product-card rule changes.
- Update `docs/WB_SEO_SOURCE_OF_TRUTH.md` when a product decision or official WB
  rule changes.
- Never report the engine as fully WB-compliant while known gaps listed in the
  source-of-truth document remain unresolved.
