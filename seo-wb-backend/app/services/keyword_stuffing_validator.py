import re
from typing import Any


class KeywordStuffingValidator:
    @classmethod
    def validate(cls, text: str) -> dict[str, Any]:
        normalized = cls._normalize(text)
        repeated_terms = cls._repeated_terms(normalized)
        density_issues: list[str] = []
        score = 100

        if "," in normalized and len(re.findall(r",", normalized)) >= 3:
            density_issues.append("Comma-separated keyword chain detected")
            score -= 20

        if repeated_terms:
            density_issues.append("Repeated nouns or adjectives detected")
            score -= min(40, len(repeated_terms) * 12)

        longest_repeat = cls._longest_repeat_chain(normalized)
        if longest_repeat >= 3:
            density_issues.append("Unnatural repeated keyword sequence detected")
            score -= min(30, (longest_repeat - 2) * 10)

        if re.search(r"\b([а-яa-z]+)\b(?:\s+\1\b){2,}", normalized, re.IGNORECASE):
            density_issues.append("Identical term repeated too many times")
            score -= 25

        return {
            "keyword_stuffing_score": max(0, min(100, score)),
            "repeated_terms": repeated_terms,
            "density_issues": density_issues,
        }

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @staticmethod
    def _repeated_terms(text: str) -> list[str]:
        counts: dict[str, int] = {}
        for token in re.split(r"[\s,.;:()/-]+", text.casefold()):
            if len(token) < 4:
                continue
            counts[token] = counts.get(token, 0) + 1
        return [token for token, count in counts.items() if count >= 2]

    @staticmethod
    def _longest_repeat_chain(text: str) -> int:
        tokens = [token for token in re.split(r"[\s,.;:()/-]+", text.casefold()) if token]
        longest = current = 1
        for idx in range(1, len(tokens)):
            if tokens[idx] == tokens[idx - 1]:
                current += 1
                longest = max(longest, current)
            else:
                current = 1
        return longest if tokens else 0
