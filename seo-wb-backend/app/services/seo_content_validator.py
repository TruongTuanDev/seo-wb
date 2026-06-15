import re
from typing import Any

from app.services.critical_attribute_validator import CriticalAttributeValidator
from app.services.keyword_stuffing_validator import KeywordStuffingValidator
from app.services.marketplace_policy_validator import MarketplacePolicyValidator
from app.services.russian_grammar_validator import RussianGrammarValidator
from app.services.semantic_consistency_validator import SemanticConsistencyValidator
from app.services.subject_rule_registry import SubjectRuleRegistry


class SeoContentValidator:
    @classmethod
    def validate(
        cls,
        *,
        title: str,
        description: str,
        seo_keyword_plan: dict[str, Any],
        confirmed_attributes: dict[str, Any] | None,
        inferred_attributes: dict[str, Any] | None,
        min_chars: int = 600,
        max_chars: int = 900,
        auto_fix: bool = True,
    ) -> dict[str, Any]:
        current_description = cls._normalize(description)
        issues: list[str] = []
        suggestions: list[str] = []
        forbidden_claims = [str(item).strip() for item in seo_keyword_plan.get("forbidden_claims", []) if str(item).strip()]
        primary_keyword = cls._normalize(seo_keyword_plan.get("primary_keyword"))
        keyword_pool = [
            primary_keyword,
            *[cls._normalize(item) for item in seo_keyword_plan.get("secondary_keywords", [])],
            *[cls._normalize(item) for item in seo_keyword_plan.get("long_tail_keywords", [])],
        ]
        keyword_pool = [item for item in keyword_pool if item]

        if len(current_description) < min_chars:
            issues.append(f"Description shorter than {min_chars} characters")
            suggestions.append("Expand description with product-specific benefits and usage context")
        if len(current_description) > max_chars:
            issues.append(f"Description longer than {max_chars} characters")
            suggestions.append("Trim low-value filler and repeated phrases")
        if primary_keyword and not cls._contains_phrase(current_description, primary_keyword):
            issues.append(f"Missing primary keyword: {primary_keyword}")
            suggestions.append("Add the primary keyword naturally to the description")

        matched_keywords = [item for item in keyword_pool[1:] if cls._contains_phrase(current_description, item)]
        if len(matched_keywords) < min(3, max(0, len(keyword_pool) - 1)):
            issues.append("Not enough secondary or long-tail keyword coverage")
            suggestions.append("Add 2-3 secondary search phrases naturally")

        if "актуальные поисковые фразы" in current_description.casefold():
            issues.append("Keyword block pattern is forbidden")
            suggestions.append("Remove keyword list blocks and keep phrases natural")

        material = cls._attr(confirmed_attributes, inferred_attributes, "composition", "Состав", "material")
        fit = cls._attr(confirmed_attributes, inferred_attributes, "fit", "Тип посадки", "Покрой")
        purpose = cls._attr(confirmed_attributes, inferred_attributes, "purpose", "Назначение")
        care = cls._attr(confirmed_attributes, inferred_attributes, "care", "Уход за вещами")

        if material and not cls._contains_any_token(current_description, material):
            issues.append("Material is missing")
            suggestions.append("Mention the material once in the description")
        if fit and not cls._contains_any_token(current_description, fit):
            issues.append("Fit or silhouette is missing")
            suggestions.append("Mention fit or silhouette once")
        if purpose and not cls._contains_any_token(current_description, purpose):
            issues.append("Use case or purpose is missing")
            suggestions.append("Add a relevant use case")
        if care and not cls._contains_any_token(current_description, care):
            suggestions.append("Optionally mention safe care guidance")

        repeated_tokens = cls._repeated_tokens(current_description)
        if repeated_tokens:
            issues.append(f"Excessive repetition: {', '.join(repeated_tokens[:3])}")
            suggestions.append("Reduce repeated words and phrases")

        if cls._is_template_like(current_description):
            issues.append("Description feels too template-like")
            suggestions.append("Make the copy more product-specific")

        forbidden_hits = [claim for claim in forbidden_claims if cls._contains_phrase(current_description, claim) or cls._contains_phrase(title, claim)]
        for hit in forbidden_hits:
            issues.append(f"Forbidden claim detected: {hit}")
        if forbidden_hits:
            suggestions.append("Remove unsupported marketing claims")

        fixed_description = current_description
        if auto_fix and issues:
            fixed_description = cls._auto_fix(
                title=title,
                description=current_description,
                primary_keyword=primary_keyword,
                keyword_pool=keyword_pool[1:],
                material=material,
                fit=fit,
                purpose=purpose,
                care=care,
                forbidden_claims=forbidden_claims,
                min_chars=min_chars,
                max_chars=max_chars,
            )

        score = cls._score(
            title=title,
            description=fixed_description,
            primary_keyword=primary_keyword,
            keyword_pool=keyword_pool,
            issues=issues,
            min_chars=min_chars,
            max_chars=max_chars,
        )
        valid = score >= 70 and not any(issue.startswith("Forbidden claim") for issue in issues)
        return {
            "valid": valid,
            "score": score,
            "issues": issues,
            "suggestions": cls._dedupe(suggestions),
            "fixed_description": fixed_description,
        }

    @classmethod
    def build_scorecard(
        cls,
        *,
        title: str,
        description: str,
        seo_keyword_plan: dict[str, Any],
        validator_result: dict[str, Any],
        confirmed_attributes: dict[str, Any] | None,
        inferred_attributes: dict[str, Any] | None,
        subject_name: str | None = None,
        wb_characteristics: list[dict[str, Any]] | None = None,
        low_confidence_attributes: list[str] | None = None,
    ) -> dict[str, Any]:
        primary_keyword = cls._normalize(seo_keyword_plan.get("primary_keyword"))
        secondary_keywords = [cls._normalize(item) for item in seo_keyword_plan.get("secondary_keywords", []) if cls._normalize(item)]
        title_score = 88 if primary_keyword and cls._contains_phrase(title, primary_keyword) else 50
        description_score = int(validator_result.get("score") or 0)
        keyword_hits = sum(1 for item in secondary_keywords if cls._contains_phrase(description, item))
        keyword_coverage_score = min(100, 55 + keyword_hits * 12 + (15 if primary_keyword and cls._contains_phrase(description, primary_keyword) else 0))
        keyword_score = keyword_coverage_score
        confirmed_count = len([value for value in (confirmed_attributes or {}).values() if value])
        inferred_count = len([value for value in (inferred_attributes or {}).values() if value])
        attributes_score = max(40, min(100, 55 + confirmed_count * 6 - max(0, inferred_count - confirmed_count) * 2))
        grammar_result = RussianGrammarValidator.validate(title)
        stuffing_result = KeywordStuffingValidator.validate(title)
        critical_result = CriticalAttributeValidator.validate(
            subject_name=subject_name,
            confirmed_attributes=confirmed_attributes,
            inferred_attributes=inferred_attributes,
            wb_characteristics=wb_characteristics,
            low_confidence_attributes=low_confidence_attributes,
        )
        semantic_result = SemanticConsistencyValidator.validate(
            subject_name=subject_name,
            title=title,
            description=description,
            confirmed_attributes=confirmed_attributes,
            inferred_attributes=inferred_attributes,
        )
        policy_result = MarketplacePolicyValidator.validate(
            subject_name=subject_name,
            title=title,
            description=description,
            confirmed_attributes=confirmed_attributes,
            inferred_attributes=inferred_attributes,
        )
        subject_rule_score = policy_result["subject_rule_score"] if SubjectRuleRegistry.resolve(subject_name) else min(65, policy_result["subject_rule_score"])
        grammar_score = grammar_result["grammar_score"]
        critical_attribute_score = critical_result["critical_score"]
        semantic_consistency_score = semantic_result["semantic_score"]
        keyword_score = max(0, int(round((keyword_score * 0.6) + (stuffing_result["keyword_stuffing_score"] * 0.4))))
        marketplace_score = int(round(
            (title_score * 0.25)
            + (grammar_score * 0.30)
            + (critical_attribute_score * 0.20)
            + (keyword_coverage_score * 0.15)
            + (attributes_score * 0.10)
        ))
        seo_score = int(round(
            (grammar_score * 0.20)
            + (marketplace_score * 0.20)
            + (subject_rule_score * 0.20)
            + (critical_attribute_score * 0.15)
            + (semantic_consistency_score * 0.15)
            + (description_score * 0.05)
            + (keyword_score * 0.05)
        ))
        blocking_issues = cls._dedupe([
            *semantic_result.get("conflicts", []),
            *policy_result.get("blocking_issues", []),
        ])
        status = (
            "needs_review"
            if blocking_issues
            else "excellent" if seo_score >= 85 else "good" if seo_score >= 70 else "needs_review" if seo_score >= 50 else "poor"
        )
        issues = [
            *validator_result.get("issues", []),
            *grammar_result.get("issues", []),
            *stuffing_result.get("density_issues", []),
            *[f'Critical attribute "{name}" is missing.' for name in critical_result.get("missing_critical_attributes", [])],
            *semantic_result.get("conflicts", []),
            *policy_result.get("blocking_issues", []),
        ]
        suggestions = [
            *validator_result.get("suggestions", []),
            *grammar_result.get("warnings", []),
            *policy_result.get("warnings", []),
            *[f'Confirm low-confidence critical attribute "{name}".' for name in critical_result.get("low_confidence_critical_attributes", [])],
        ]
        return {
            "seo_score": seo_score,
            "title_score": int(title_score),
            "description_score": int(description_score),
            "attributes_score": int(attributes_score),
            "keyword_coverage_score": int(keyword_coverage_score),
            "keyword_score": int(keyword_score),
            "grammar_score": int(grammar_score),
            "marketplace_score": int(marketplace_score),
            "subject_rule_score": int(subject_rule_score),
            "critical_attribute_score": int(critical_attribute_score),
            "semantic_consistency_score": int(semantic_consistency_score),
            "keyword_stuffing_score": int(stuffing_result["keyword_stuffing_score"]),
            "missing_critical_attributes": critical_result.get("missing_critical_attributes", []),
            "low_confidence_critical_attributes": critical_result.get("low_confidence_critical_attributes", []),
            "semantic_conflicts": semantic_result.get("conflicts", []),
            "blocking_issues": blocking_issues,
            "issues": cls._dedupe(issues),
            "suggestions": cls._dedupe(suggestions),
            "status": status,
        }

    @staticmethod
    def _auto_fix(
        *,
        title: str,
        description: str,
        primary_keyword: str,
        keyword_pool: list[str],
        material: str | None,
        fit: str | None,
        purpose: str | None,
        care: str | None,
        forbidden_claims: list[str],
        min_chars: int,
        max_chars: int,
    ) -> str:
        result = description
        if title and not SeoContentValidator._contains_phrase(result, title):
            result = f"{title}. {result}".strip()
        additions: list[str] = []
        if material and not SeoContentValidator._contains_any_token(result, material):
            additions.append(f"Материал: {material}.")
        if fit and not SeoContentValidator._contains_any_token(result, fit):
            additions.append(f"Посадка и силуэт: {fit}.")
        if purpose and not SeoContentValidator._contains_any_token(result, purpose):
            additions.append(f"Подходит для сценариев: {purpose}.")
        if care and not SeoContentValidator._contains_any_token(result, care):
            additions.append(f"Уход: {care}.")
        if additions:
            result = SeoContentValidator._normalize(" ".join([result, *additions]))
        for claim in forbidden_claims:
            result = re.sub(re.escape(claim), "", result, flags=re.IGNORECASE)
        if len(result) < min_chars:
            additions = [
                "Продуманный крой поддерживает комфорт в движении и помогает изделию аккуратно выглядеть в течение дня.",
                "Практичная модель легко сочетается с базовыми вещами гардероба и подходит для регулярной носки.",
                "Бережный уход помогает дольше сохранять форму изделия и свойства материала.",
            ]
            for addition in additions:
                if len(result) >= min_chars:
                    break
                if not SeoContentValidator._contains_phrase(result, addition):
                    result = SeoContentValidator._normalize(f"{result} {addition}")
        return result[:max_chars].strip()

    @staticmethod
    def _contains_phrase(text: str, phrase: str) -> bool:
        return SeoContentValidator._normalize(phrase).casefold() in SeoContentValidator._normalize(text).casefold()

    @staticmethod
    def _contains_any_token(text: str, value: str) -> bool:
        text_tokens = {token.casefold() for token in re.split(r"[\s,.;:()/-]+", text) if token}
        value_tokens = [token.casefold() for token in re.split(r"[\s,.;:()/-]+", value) if token]
        return any(token in text_tokens for token in value_tokens)

    @staticmethod
    def _normalize(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @staticmethod
    def _attr(confirmed: dict[str, Any] | None, inferred: dict[str, Any] | None, *keys: str) -> str | None:
        for source in (confirmed or {}, inferred or {}):
            for key in keys:
                value = source.get(key)
                if isinstance(value, list):
                    joined = ", ".join(str(item).strip() for item in value if str(item).strip())
                    if joined:
                        return joined
                if value is not None and str(value).strip():
                    return str(value).strip()
        return None

    @staticmethod
    def _repeated_tokens(text: str) -> list[str]:
        counts: dict[str, int] = {}
        for token in re.split(r"[\s,.;:()/-]+", text.casefold()):
            if len(token) < 5:
                continue
            counts[token] = counts.get(token, 0) + 1
        return [token for token, count in counts.items() if count >= 4]

    @staticmethod
    def _is_template_like(text: str) -> bool:
        template_markers = [
            "без лишних обещаний",
            "в своей категории",
            "поддерживает релевантные поисковые запросы",
        ]
        hits = sum(1 for marker in template_markers if marker in text.casefold())
        return hits >= 2

    @staticmethod
    def _score(
        *,
        title: str,
        description: str,
        primary_keyword: str,
        keyword_pool: list[str],
        issues: list[str],
        min_chars: int,
        max_chars: int,
    ) -> int:
        score = 100
        if not primary_keyword or not SeoContentValidator._contains_phrase(title, primary_keyword):
            score -= 12
        if not primary_keyword or not SeoContentValidator._contains_phrase(description, primary_keyword):
            score -= 12
        secondary_hits = sum(1 for item in keyword_pool[1:] if SeoContentValidator._contains_phrase(description, item))
        if secondary_hits < 3:
            score -= (3 - secondary_hits) * 6
        if len(description) < min_chars:
            score -= 18
        if len(description) > max_chars:
            score -= 10
        score -= len([issue for issue in issues if issue.startswith("Forbidden claim")]) * 25
        score -= len([issue for issue in issues if issue.startswith("Excessive repetition")]) * 8
        return max(0, min(100, score))

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return result
