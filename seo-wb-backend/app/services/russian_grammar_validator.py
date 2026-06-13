import re
from typing import Any


class RussianGrammarValidator:
    _BROKEN_PATTERNS = [
        re.compile(r"\b(женский|мужской)\s+(высокая|лето|хлопок|голубой)\b", re.IGNORECASE),
        re.compile(r"\b(джинсы|футболка|платье)\s+(женский|мужской)\s+(лето|хлопок|белый|голубой)\b", re.IGNORECASE),
        re.compile(r"\b(актуальные поисковые фразы|релевантные поисковые запросы)\b", re.IGNORECASE),
    ]

    @classmethod
    def validate(cls, text: str) -> dict[str, Any]:
        normalized = cls._normalize(text)
        issues: list[str] = []
        warnings: list[str] = []
        score = 100

        for pattern in cls._BROKEN_PATTERNS:
            if pattern.search(normalized):
                issues.append("Broken Russian phrase or noun-adjective agreement issue detected")
                score -= 35

        repeated = cls._repeated_tokens(normalized)
        if repeated:
            warnings.append(f"Repeated words: {', '.join(repeated[:3])}")
            score -= min(18, len(repeated) * 6)

        chain_size = cls._unnatural_keyword_chain(normalized)
        if chain_size >= 4:
            issues.append("Unnatural keyword chain detected")
            score -= min(30, (chain_size - 3) * 8)

        if re.search(r"\b(женский|мужской|лето|зима|хлопок|голубой|белый|черный)\b(?:\s+\b(женский|мужской|лето|зима|хлопок|голубой|белый|черный)\b){2,}", normalized, re.IGNORECASE):
            issues.append("Marketplace spam pattern detected")
            score -= 20

        spam_detected = any("spam" in item.casefold() or "chain" in item.casefold() for item in issues)
        score = max(0, min(100, score))
        return {
            "grammar_score": score,
            "issues": issues,
            "warnings": warnings,
            "spam_detected": spam_detected,
        }

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @staticmethod
    def _repeated_tokens(text: str) -> list[str]:
        counts: dict[str, int] = {}
        for token in re.split(r"[\s,.;:()/-]+", text.casefold()):
            if len(token) < 4:
                continue
            counts[token] = counts.get(token, 0) + 1
        return [token for token, count in counts.items() if count >= 3]

    @staticmethod
    def _unnatural_keyword_chain(text: str) -> int:
        tokens = [token for token in re.split(r"[\s,.;:()/-]+", text.casefold()) if token]
        lexical = {"женский", "мужской", "лето", "зима", "хлопок", "голубой", "белый", "черный", "высокая", "широкие"}
        longest = current = 0
        for token in tokens:
            if token in lexical:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        return longest
