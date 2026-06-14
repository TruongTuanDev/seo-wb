 # WB Fashion SEO Source of Truth

Last verified: 2026-06-14

This document defines how this project must generate Wildberries fashion
product cards. It exists to prevent AI agents and future code changes from
drifting back to generic SEO practices, keyword stuffing, or rules intended
for a single fashion category.

Normative words:

- `MUST`: required behavior.
- `MUST NOT`: forbidden behavior.
- `SHOULD`: preferred behavior unless a subject-specific WB rule requires
  something else.

## 1. Product vision

The system is intended for most fashion subjects on Wildberries, not only
jeans or trousers.

The user flow is:

1. Upload front and back product images.
2. Select or confirm the detected WB subject.
3. Optionally add a short note.
4. Generate the complete card.

The seller must not be forced to manually write SEO fields. The backend must:

1. Analyze the images.
2. Resolve a real WB `subjectID`.
3. Load the current WB characteristics for that subject.
4. Infer attributes with confidence information.
5. Build a subject-aware keyword plan.
6. Generate title and description.
7. Generate one variant per detected/selected color.
8. Validate grammar, subject rules, characteristics, and semantic consistency.
9. Auto-fix repairable problems.
10. Validate again before returning the draft.

The user should receive the repaired result, not raw AI output.

## 2. Authority order

When sources disagree, use this order:

1. Current official WB API response for the selected `subjectID`.
2. Current official WB seller instructions and WB API documentation.
3. Product decisions in this document.
4. Subject rules in `SubjectRuleRegistry`.
5. Family fallback rules.
6. Model prompts, old tests, comments, and generic SEO knowledge.

An old prompt or test is not authoritative if it conflicts with a higher source.

## 3. Official sources

Use official Wildberries sources only when validating WB-specific behavior:

- Product-card creation rules:
  https://seller.wildberries.ru/instructions/ru/am/material/how-to-create-a-product-card-armenia
- WB Content API:
  https://dev.wildberries.ru/en/docs/openapi/work-with-products
- Product-card API changes and required characteristics:
  https://dev.wildberries.ru/en/release-notes?id=498
- Current redirected card-field rules page:
  https://seller.wildberries.ru/instructions/ru/ru/material/card-creation-rules

Important facts verified on 2026-06-14:

- WB title length is at most 60 characters.
- The title should briefly and accurately answer what is shown in the card.
- WB advises against gender/age, brand, season, composition, repetitions,
  synonyms, unrelated detail, keyword chains, and special-symbol spam in title.
- Description length depends on the parent category. The Content API documents
  a category-dependent limit rather than one universal limit.
- Required characteristics can change. The current
  `GET /content/v2/object/charcs/{subjectId}` response is authoritative.
- Filter-critical characteristics can be identified from WB metadata such as
  `required` and `hasFilter`.

Re-check these sources before changing a marketplace rule that may have changed
since the verification date.

## 4. Project title rules

These are hard product requirements.

Title `MUST`:

- be Russian;
- start with or clearly identify the resolved WB subject;
- describe only the essential product type and high-value model detail;
- use natural Russian grammar;
- be no longer than 60 characters;
- be generated from the subject rule when one exists;
- use a conservative family fallback for unknown subjects.

Title `MUST NOT` contain:

- gender or target audience;
- age;
- color;
- brand;
- season;
- composition or material;
- raw SEO keyword chains;
- duplicated subject words;
- unsupported claims;
- comma-separated synonyms;
- slash-separated alternative product names.

Examples:

- Good: `Джинсы широкие с высокой посадкой рваные`
- Good: `Брюки широкие с высокой посадкой`
- Bad: `Джинсы женские голубые хлопок лето`
- Bad: `Брюки Высокая Бежевый`

Gender, color, material, season, and audience belong in WB characteristics.

The admin setting `include_gender_in_title` is legacy. It must not override this
rule.

## 5. Project description rules

Description `MUST`:

- be Russian, natural, truthful, and specific to the resolved subject;
- match the title and characteristics;
- describe product construction, fit, material, comfort, use cases, and safe
  care guidance when supported;
- use keywords only when they fit naturally;
- stay within the current category limit returned or documented by WB;
- avoid claims that cannot be verified from images or seller input.

Description `MUST NOT` contain:

- a concrete color name;
- gender inserted only for SEO;
- a raw keyword list or an AI/SEO meta sentence;
- another product subject used as if it were the current product;
- contradictory material, fit, rise, construction, or quantity;
- generic filler written only to reach a fixed character count;
- unsupported superlatives, certifications, originality, or guarantees.

Forbidden patterns include:

- `Актуальные поисковые фразы: ...`
- `В описании естественно раскрыты детали модели: ...`
- `Описание раскрывает материал, посадку...`
- repeated filler paragraphs

Mentioning another garment as a styling companion is allowed only when it
cannot be confused with the product itself. Semantic validation must distinguish
`сочетается с джинсами` from incorrectly calling trousers `джинсы`.

Project-specific decision: do not mention color in the description, even when
generic marketplace SEO advice would allow it. Color is represented by the
variant characteristic.

## 6. Subject-driven behavior

Subject rules are implemented in:

- `seo-wb-backend/app/services/subject_rule_registry.py`

Every supported rule should define:

- subject code and Russian names;
- family fallback;
- title pattern;
- description blueprint;
- critical attributes;
- forbidden terms;
- semantic conflicts;
- safe inference rules;
- SEO priorities.

Initial coverage must remain at least:

- jeans;
- trousers;
- leggings;
- skirt;
- dress;
- t-shirt;
- shirt;
- hoodie;
- sweatshirt;
- jacket;
- coat;
- bra;
- panties;
- pajama;
- shorts.

Adding a subject requires tests for its title, description, critical
characteristics, and at least one semantic conflict.

## 7. Characteristics and confidence

The engine `MUST` load WB characteristics for the resolved `subjectID`.

Rules:

- Use exact WB characteristic IDs and accepted dictionary values.
- Never invent a characteristic ID.
- `required=true` characteristics must be satisfied before push when a reliable
  value is available.
- Give special priority to `required=true` and `hasFilter=true`.
- Invalid dictionary values must be normalized to an allowed WB value or
  removed.
- User-confirmed attributes must never be overwritten by inference.
- High-risk inferred fields must remain low-confidence until confirmed when
  images cannot prove them.

High-risk examples:

- exact composition;
- lining material;
- exact season;
- closure hidden from images;
- bra wire/support construction;
- set quantity not visible;
- claims about fabric properties.

Do not silently invent missing critical attributes merely to increase an SEO
score.

## 8. Color variants and seller article

Each color variant `MUST` have:

- its own `Цвет` characteristic;
- a seller article suffix derived from that same final characteristic;
- a Russian display value in the suffix.

Format:

```text
{base_vendor_code}/{RussianColor}
```

Examples:

```text
234/Синий
234/Красный
234/Фиолетовый
234/Желтый
```

The suffix must be calculated after the final variant characteristics are
known. It must not depend only on a global image-analysis color.

Title and description remain common and color-neutral across variants.

## 9. Keyword planning

Keyword planning is an internal aid, not a requirement to paste phrases
verbatim.

The primary keyword `MUST` be compatible with title rules. It must not include
gender, color, brand, season, or material when the title forbids those fields.

Secondary and long-tail keywords may support description planning, but:

- forbidden title fields must not be required in title validation;
- color must not be required in description validation;
- keyword coverage must not override semantic correctness;
- a missing exact phrase is not an error when the natural Russian inflection
  communicates the same intent;
- search phrases must not be emitted as a keyword block.

The engine must never enter a repair loop caused by its keyword plan
contradicting its title or description policy.

## 10. Validation and scoring

Validation should cover:

- title policy;
- Russian grammar;
- keyword stuffing;
- subject-rule compliance;
- critical WB characteristics;
- dictionary validity;
- semantic consistency;
- description quality;
- variant/color consistency.

Semantic conflicts that identify the product as another subject are blocking
errors, not minor score deductions.

Examples of blocking conflicts:

- subject `Брюки`, text calls the product `джинсы`;
- subject `Юбка`, text calls the product `платье`;
- linen characteristic, text claims denim;
- wide fit, text claims skinny;
- high rise, text claims low rise;
- variant article says `Синий`, characteristic says `Красный`.

An aggregate SEO score is diagnostic only. A high score must never allow a
blocking conflict, invalid required characteristic, or forbidden title field
to pass.

`subject_rule_score` must measure compliance with the rule. It must not be 100
merely because a registry entry exists.

## 11. Auto-fix contract

Required pipeline:

```text
generate
-> normalize WB characteristics
-> validate
-> auto-fix repairable copy
-> normalize variants and vendor codes
-> validate again
-> return draft
```

Auto-fix may:

- rebuild a title from the subject rule;
- regenerate description from the subject blueprint;
- remove forbidden claims and keyword blocks;
- remove color and gender from copy;
- normalize accepted dictionary values;
- repair vendor-code color suffixes.

Auto-fix must not:

- change the selected store, category, or subject silently;
- change uploaded media or regenerate images;
- overwrite seller-confirmed attributes;
- invent an uncertain product fact;
- hide a blocking conflict by increasing unrelated score components.

## 12. Implementation status as of 2026-06-14

Implemented and covered by focused regression tests:

1. Keyword planning keeps gender, color, material, brand, and season out of the
   primary title keyword.
2. OpenAI prompts, subject title patterns, and deterministic title templates
   follow the project title policy.
3. Generated and retained descriptions are sanitized for concrete colors and
   SEO/AI meta sentences.
4. `subject_rule_score` measures actual policy compliance.
5. Semantic and marketplace-policy conflicts are blocking and prevent an
   `excellent` or `good` status.
6. Scorecards receive live WB characteristics and include live
   `required=true` fields.
7. Dictionary-backed characteristics are normalized or removed when invalid.
8. Vendor-code color suffixes are recalculated from final enriched
   characteristics.
9. Required live WB characteristics are enforced before push.

Remaining integration gaps:

1. Description defaults are still fixed at 600-900 because the current subject
   metadata integration does not expose a reliable category-specific
   description limit.
2. Russian morphology checks are deterministic and conservative; they do not
   replace a full morphology service for every possible inflected attribute
   value.
3. Some legacy admin flags remain in configuration for backward compatibility,
   even though the mandatory generate/validate/repair pipeline must not be
   disabled.

## 13. Required tests

At minimum, changes to card SEO must verify:

- title excludes gender, age, color, brand, season, and material;
- title is at most 60 characters;
- subject title patterns produce natural Russian;
- trousers copy does not identify the product as jeans;
- skirt copy does not identify the product as a dress;
- description contains no concrete color;
- description contains no keyword block or AI meta sentence;
- semantic conflicts block acceptance;
- critical attributes use live WB characteristic names/IDs;
- invalid dictionary values are removed or normalized;
- low-confidence critical attributes are surfaced;
- confirmed attributes are preserved;
- each color variant has matching `Цвет` and vendor-code suffix;
- unknown subjects still use a safe fallback.

Focused backend command:

```powershell
cd seo-wb-backend
.\.venv\Scripts\python.exe -m pytest `
  tests/test_seo_engine.py `
  tests/test_wb_marketplace_quality.py `
  tests/test_subject_driven_engine.py `
  tests/test_product_copy_quality.py `
  tests/test_card_generator.py `
  tests/test_card_payload_enricher.py -q
```

The full suite may require local PostgreSQL, Redis, or service configuration.
Report infrastructure failures separately from product-rule failures.

## 14. Change checklist for AI agents

Before editing:

- Read this document.
- Identify the resolved subject and affected WB characteristics.
- Check whether the rule is official WB behavior or a project-specific decision.

Before finishing:

- Confirm title and description policies do not conflict with keyword planning.
- Confirm final payload characteristics, not intermediate analysis, drive
  variant identifiers.
- Run focused tests.
- State any remaining known gaps honestly.
- Update this document if the product decision or official WB behavior changed.

Do not use an external AI score as proof of compliance. Use it as feedback,
reproduce the issue locally, and encode the accepted rule in deterministic
validation and tests.
