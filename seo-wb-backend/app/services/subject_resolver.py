import json
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

from google import genai
from google.genai import types
from openai import OpenAI

from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.card import ImageAnalysis, ProductInput


AI_RESOLUTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "candidates": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "subjectName": {"type": "STRING"},
                    "confidence": {"type": "NUMBER"},
                    "reason": {"type": "STRING"},
                },
            },
        },
        "searchTerms": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
}


class SubjectResolver:
    def __init__(self, settings: Settings, wb_client: Any):
        self._settings = settings
        self._wb = wb_client

    async def resolve(self, user_input: ProductInput, analysis: ImageAnalysis) -> dict[str, Any]:
        subjects = await self._wb.get_subjects(parent_id=None, locale="ru")
        if user_input.subject_id:
            for subject in subjects:
                if int(subject.get("subjectID", 0)) == user_input.subject_id:
                    return subject
            raise AppError("subject_not_found", "Provided subject_id was not found in Wildberries subjects.", 422)

        source_text = self._source_text(user_input, analysis)
        if not source_text:
            raise AppError(
                "subject_resolution_failed",
                "Could not infer Wildberries subject from image/user input. Select a subject manually.",
                422,
            )

        deterministic = self._best_deterministic_match(subjects, source_text)
        if deterministic and deterministic[0] >= 0.70:
            return deterministic[1]

        ai_match = self._resolve_with_ai(subjects, source_text)
        if ai_match:
            return ai_match

        if deterministic and deterministic[0] >= 0.62:
            return deterministic[1]

        raise AppError(
            "subject_resolution_failed",
            "Could not map product description to a Wildberries subject. Select a subject manually.",
            422,
            {
                "input": source_text[:500],
                "top_candidates": self._top_candidate_details(subjects, source_text),
            },
        )

    @staticmethod
    def _source_text(user_input: ProductInput, analysis: ImageAnalysis) -> str:
        parts = [
            user_input.category,
            user_input.note,
            analysis.category,
            analysis.product_name,
            analysis.material,
            analysis.gender,
            " ".join(analysis.features or []),
        ]
        return " ".join(str(part).strip() for part in parts if part).strip()

    def _resolve_with_ai(self, subjects: list[dict[str, Any]], source_text: str) -> dict[str, Any] | None:
        payload = {
            "task": "Resolve a marketplace product description to exactly one Wildberries subject.",
            "rules": [
                "Input may be Vietnamese, Russian, English, transliterated, misspelled, or mixed language.",
                "Choose only subjectName values that are present in allowed_subjects.",
                "Prefer the concrete product type over attributes such as color, size, gender, SKU, fit, or package dimensions.",
                "Return 0 candidates if no allowed subject is plausible.",
            ],
            "product_description": source_text[:1200],
            "allowed_subjects": self._subject_options(subjects),
        }
        raw = None
        if self._settings.openai_api_key and self._settings.openai_card_model:
            raw = self._resolve_with_openai(payload)
        if raw is None and self._settings.gemini_api_key:
            raw = self._resolve_with_gemini(payload)
        if not raw:
            return None
        return self._verified_ai_match(subjects, raw)

    def _resolve_with_openai(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        try:
            client = OpenAI(api_key=self._settings.openai_api_key)
            response = client.chat.completions.create(
                model=self._settings.openai_card_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a multilingual product taxonomy resolver. "
                            "Return JSON only and never invent subject names."
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "subject_resolution",
                        "schema": AI_RESOLUTION_SCHEMA,
                        "strict": False,
                    },
                },
                temperature=0,
            )
            return json.loads(response.choices[0].message.content or "{}")
        except Exception:
            return None

    def _resolve_with_gemini(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        try:
            client = genai.Client(api_key=self._settings.gemini_api_key)
            response = client.models.generate_content(
                model=self._settings.gemini_model,
                contents=[
                    "Resolve the product description to the best Wildberries subject. Return JSON only.",
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=AI_RESOLUTION_SCHEMA,
                    temperature=0,
                ),
            )
            return json.loads(response.text or "{}")
        except Exception:
            return None

    @staticmethod
    def _verified_ai_match(subjects: list[dict[str, Any]], raw: dict[str, Any]) -> dict[str, Any] | None:
        by_name = {str(subject.get("subjectName", "")).casefold(): subject for subject in subjects}
        candidates = raw.get("candidates") if isinstance(raw, dict) else None
        if not isinstance(candidates, list):
            return None
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            name = str(candidate.get("subjectName") or "").casefold().strip()
            try:
                confidence = float(candidate.get("confidence") or 0)
            except (TypeError, ValueError):
                confidence = 0
            if confidence >= 0.55 and name in by_name:
                return by_name[name]
        return None

    @classmethod
    def _best_deterministic_match(cls, subjects: list[dict[str, Any]], source_text: str) -> tuple[float, dict[str, Any]] | None:
        source_key = cls._normalize_text(cls._strip_noise(source_text))
        source_tokens = set(cls._tokens(source_key))
        if not source_key:
            return None
        scored: list[tuple[float, dict[str, Any]]] = []
        for subject in subjects:
            score = cls._deterministic_score(source_key, source_tokens, str(subject.get("subjectName") or ""))
            scored.append((score, subject))
        return max(scored, key=lambda item: item[0], default=None)

    @classmethod
    def _top_candidate_details(cls, subjects: list[dict[str, Any]], source_text: str) -> list[dict[str, Any]]:
        source_key = cls._normalize_text(cls._strip_noise(source_text))
        source_tokens = set(cls._tokens(source_key))
        scored = []
        for subject in subjects:
            subject_name = str(subject.get("subjectName") or "")
            score = cls._deterministic_score(source_key, source_tokens, subject_name)
            scored.append({"subjectID": subject.get("subjectID"), "subjectName": subject_name, "score": round(score, 3)})
        return sorted(scored, key=lambda item: item["score"], reverse=True)[:5]

    @classmethod
    def _deterministic_score(cls, source_key: str, source_tokens: set[str], subject_name: str) -> float:
        subject_key = cls._normalize_text(subject_name)
        if not source_key or not subject_key:
            return 0
        subject_tokens = set(cls._tokens(subject_key))
        score = SequenceMatcher(None, source_key, subject_key).ratio()
        if subject_key in source_key:
            score = max(score, 0.68)
        if source_key in subject_key:
            score = max(score, 0.76)
        if subject_tokens:
            score = max(score, len(source_tokens & subject_tokens) / len(subject_tokens))
        return score

    @staticmethod
    def _subject_options(subjects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {"subjectID": subject.get("subjectID"), "subjectName": subject.get("subjectName")}
            for subject in subjects
            if subject.get("subjectID") and subject.get("subjectName")
        ][:1500]

    @staticmethod
    def _strip_noise(value: str) -> str:
        value = " ".join(str(value or "").casefold().split())
        value = re.sub(
            r"\b(?:m\u00e3|ma|sku|article|vendor|\u0430\u0440\u0442(?:\u0438\u043a\u0443\u043b)?)"
            r"\s*[:#-]?\s*[\w-]+",
            " ",
            value,
        )
        value = re.sub(
            r"\b(?:size|\u0440\u0430\u0437\u043c\u0435\u0440|k\u00edch th\u01b0\u1edbc|kich thuoc|"
            r"c\u00e2n n\u1eb7ng|can nang|weight)\b",
            " ",
            value,
        )
        value = re.sub(r"\b\d+(?:[x\u0445\u00d7]\d+){1,3}\b", " ", value)
        value = re.sub(r"\b\d+(?:[.,]\d+)?(?:-\d+)?\b", " ", value)
        return re.sub(r"[,;/()]+", " ", value)

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value.casefold())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = normalized.replace("đ", "d").replace("ё", "е")
        normalized = re.sub(r"[^\w\sа-яА-Я]+", " ", normalized, flags=re.UNICODE)
        return " ".join(normalized.split())

    @staticmethod
    def _tokens(value: str) -> list[str]:
        return [token for token in value.split() if len(token) > 1]
