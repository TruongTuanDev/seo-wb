from typing import Any

from app.schemas.card import ImageAnalysis, ProductInput
from app.services.product_copy_policy import suggest_characteristics


CHARC_ALIASES = {
    "composition": ["Состав"],
    "color": ["Цвет"],
    "gender": ["Пол"],
    "season": ["Сезон"],
    "fit": ["Тип посадки"],
    "pants_model": ["Модель джинсов", "Модель брюк", "Покрой"],
    "closure": ["Вид застежки", "Тип застежки"],
    "pockets": ["Тип карманов"],
    "features": ["Особенности модели"],
    "purpose": ["Назначение"],
    "contents": ["Комплектация"],
    "underwear_features": ["Особенности белья"],
    "age_limits": ["Возрастные ограничения"],
    "insulation": ["Утеплитель"],
    "care": ["Уход за вещами"],
    "pattern": ["Рисунок"],
    "texture": ["Фактура материала"],
    "growth_type": ["Тип ростовки"],
    "decor": ["Декоративные элементы"],
    "lining": ["Материал подкладки"],
    "neckline": ["Вырез горловины"],
    "sleeve_type": ["Тип рукава"],
    "tnved": ["ТНВЭД", "ТН ВЭД", "Код ТНВЭД", "Код ТН ВЭД"],
}

STRICT_SKIP_NAMES = {
    "Номер декларации соответствия",
    "Номер сертификата соответствия",
    "Дата регистрации сертификата/декларации",
    "Дата окончания действия сертификата/декларации",
    "Любимые герои",
}

HIGH_RISK_ALIASES = {
    "composition",
    "color",
    "gender",
    "season",
    "pattern",
    "texture",
    "lining",
}


class CardPayloadEnricher:
    def __init__(self, charcs: list[dict[str, Any]], directories: dict[str, list[Any]] | None = None):
        self._charcs = charcs
        self._directories = directories or {}
        self._by_id = {int(item["charcID"]): item for item in charcs if item.get("charcID")}
        self._by_name = {
            self._norm_name(item.get("name")): item
            for item in charcs
            if item.get("charcID") and item.get("name")
        }

    def enrich_payload(
        self,
        payload: Any,
        *,
        subject_id: int,
        tnved: dict[str, Any] | None = None,
        user_input: ProductInput | None = None,
        analysis: ImageAnalysis | None = None,
    ) -> Any:
        for variant in self._iter_variants(payload):
            self.enrich_variant(variant, subject_id=subject_id, tnved=tnved, user_input=user_input, analysis=analysis)
        return payload

    def build_attribute_confidence(
        self,
        *,
        subject_id: int,
        user_input: ProductInput | None,
        analysis: ImageAnalysis | None,
    ) -> dict[str, Any]:
        values = self._infer_values(subject_id=subject_id, user_input=user_input, analysis=analysis)
        confirmed_attributes: dict[str, Any] = {}
        inferred_attributes: dict[str, Any] = {}
        missing_attributes: list[str] = []
        low_confidence_attributes: list[str] = []

        user_attrs = dict(user_input.attributes or {}) if user_input else {}
        seo_inputs = user_input.seo_inputs if user_input else None
        for alias, value in values.items():
            if not value:
                if alias in {"composition", "color", "gender", "season", "purpose"}:
                    missing_attributes.append(alias)
                continue
            is_confirmed = self._is_confirmed(
                alias,
                value,
                user_input=user_input,
                analysis=analysis,
                user_attrs=user_attrs,
                seo_inputs=seo_inputs,
            )
            if is_confirmed:
                confirmed_attributes[alias] = value
            else:
                inferred_attributes[alias] = value
                if alias in HIGH_RISK_ALIASES:
                    low_confidence_attributes.append(alias)

        return {
            "confirmed_attributes": confirmed_attributes,
            "inferred_attributes": inferred_attributes,
            "missing_attributes": missing_attributes,
            "low_confidence_attributes": low_confidence_attributes,
        }

    def enrich_variant(
        self,
        variant: dict[str, Any],
        *,
        subject_id: int,
        tnved: dict[str, Any] | None = None,
        user_input: ProductInput | None = None,
        analysis: ImageAnalysis | None = None,
    ) -> None:
        self._drop_unknown_characteristics(variant)
        if tnved and tnved.get("tnved"):
            variant["tnved"] = str(tnved["tnved"])
            self._upsert_by_alias(variant, "tnved", [str(tnved["tnved"])], overwrite=True)
            if tnved.get("isKiz") is True:
                variant["kizMarked"] = True

        values = self._infer_values(subject_id=subject_id, user_input=user_input, analysis=analysis)
        confidence = self.build_attribute_confidence(subject_id=subject_id, user_input=user_input, analysis=analysis)
        low_confidence = set(confidence.get("low_confidence_attributes", []))
        for alias, value in values.items():
            if value:
                if alias in low_confidence:
                    continue
                self._upsert_by_alias(
                    variant,
                    alias,
                    value,
                    overwrite=alias in {"composition", "gender", "season", "fit", "purpose", "underwear_features", "age_limits"},
                )
        self._conform_characteristics(variant)

    def _infer_values(
        self,
        *,
        subject_id: int,
        user_input: ProductInput | None,
        analysis: ImageAnalysis | None,
    ) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if user_input:
            attrs.update(user_input.attributes or {})
        if analysis:
            attrs.update(analysis.attributes or {})
        for key, value in suggest_characteristics({"subjectID": subject_id}, analysis, user_input).items():
            attrs.setdefault(key, value)

        features = [str(item) for item in (analysis.features if analysis else []) if item]
        all_text = " ".join([*features, *[f"{key} {value}" for key, value in attrs.items()]]).casefold()

        return {
            "composition": self._first(attrs, ["Состав"]) or (analysis.material if analysis else None),
            "color": self._first(attrs, ["Цвет"]) or (analysis.color if analysis else None) or (user_input.color if user_input else None),
            "gender": self._first(attrs, ["Пол"]) or (analysis.gender if analysis else None) or (user_input.gender if user_input else None),
            "season": self._first(attrs, ["Сезон"]) or (analysis.season if analysis else None),
            "fit": self._first(attrs, ["Тип посадки"]) or self._fit_value(analysis.fit_type if analysis else None, all_text),
            "pants_model": self._first(attrs, ["Модель джинсов", "Модель брюк", "Покрой"]) or self._pants_model(all_text),
            "closure": self._first(attrs, ["Вид застежки", "Тип застежки"]) or self._closure(all_text, subject_id=subject_id),
            "pockets": self._first(attrs, ["Тип карманов"]) or self._pockets(all_text),
            "features": self._first(attrs, ["Особенности модели"]) or self._features(features),
            "purpose": self._first(attrs, ["Назначение", "purpose"]) or self._default_purpose(all_text),
            "contents": self._first(attrs, ["Комплектация"]) or self._contents(subject_id),
            "underwear_features": self._first(attrs, ["Особенности белья", "underwear_features"]),
            "age_limits": self._first(attrs, ["Возрастные ограничения", "age_limits"]),
            "insulation": self._first(attrs, ["Утеплитель"]) or "без утеплителя",
            "care": self._first(attrs, ["Уход за вещами"]) or self._care_value(all_text),
            "pattern": self._first(attrs, ["Рисунок"]) or self._pattern_value(all_text, subject_id=subject_id),
            "texture": self._first(attrs, ["Фактура материала"]) or self._texture_value(attrs, analysis, all_text),
            "growth_type": self._first(attrs, ["Тип ростовки"]) or "для среднего роста",
            "decor": self._first(attrs, ["Декоративные элементы"]) or self._decor_value(all_text),
            "lining": self._first(attrs, ["Материал подкладки"]) or "без подкладки",
            "neckline": self._first(attrs, ["Вырез горловины"]) or self._neckline_value(all_text),
            "sleeve_type": self._first(attrs, ["Тип рукава"]) or self._sleeve_value(all_text),
        }

    def _upsert_by_alias(self, variant: dict[str, Any], alias: str, value: Any, *, overwrite: bool = True) -> None:
        charc = self._find_charc(alias)
        if not charc:
            return
        self._upsert(variant, int(charc["charcID"]), self._normalize_dictionary_value(alias, value), overwrite=overwrite)

    def _find_charc(self, alias: str) -> dict[str, Any] | None:
        for name in CHARC_ALIASES[alias]:
            found = self._by_name.get(self._norm_name(name))
            if found and str(found.get("name") or "") not in STRICT_SKIP_NAMES:
                return found
        return None

    def _drop_unknown_characteristics(self, variant: dict[str, Any]) -> None:
        valid = []
        seen = set()
        for item in variant.get("characteristics") or []:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            charc_id = int(item["id"])
            if charc_id not in self._by_id or charc_id in seen:
                continue
            seen.add(charc_id)
            valid.append({"id": charc_id, "value": self._limit_value(charc_id, self._normalize_value(item.get("value")))})
        variant["characteristics"] = valid

    def _conform_characteristics(self, variant: dict[str, Any]) -> None:
        valid = []
        seen = set()
        for item in variant.get("characteristics") or []:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            charc_id = int(item["id"])
            if charc_id not in self._by_id or charc_id in seen:
                continue
            alias = self._alias_for_charc_id(charc_id)
            value = (
                self._normalize_dictionary_value(alias, item.get("value"))
                if alias
                else self._normalize_value(item.get("value"))
            )
            value = self._limit_value(charc_id, value)
            if value == []:
                continue
            seen.add(charc_id)
            valid.append({"id": charc_id, "value": value})
        variant["characteristics"] = valid

    def _alias_for_charc_id(self, charc_id: int) -> str | None:
        charc_name = self._norm_name(self._by_id.get(charc_id, {}).get("name"))
        for alias, names in CHARC_ALIASES.items():
            if any(self._norm_name(name) == charc_name for name in names):
                return alias
        return None

    def _limit_value(self, charc_id: int, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        max_count = int(self._by_id.get(charc_id, {}).get("maxCount") or 0)
        return value[:max_count] if max_count > 0 else value

    def _normalize_dictionary_value(self, alias: str, value: Any) -> Any:
        normalized = self._normalize_value(value)
        allowed_values = self._directory_values(alias)
        if not allowed_values or not isinstance(normalized, list):
            return normalized

        matched_values: list[str] = []
        for item in normalized:
            match = self._match_dictionary_item(alias, item, allowed_values)
            if match and match not in matched_values:
                matched_values.append(match)
        return matched_values

    def _directory_values(self, alias: str) -> list[str]:
        values = self._directories.get(alias) or []
        normalized_values: list[str] = []
        for item in values:
            if isinstance(item, dict):
                raw = item.get("name") or item.get("value") or item.get("title")
            else:
                raw = item
            text = str(raw or "").strip()
            if text:
                normalized_values.append(text)
        return normalized_values

    @classmethod
    def _match_dictionary_item(cls, alias: str, value: Any, allowed_values: list[str]) -> str | None:
        source = cls._norm_dict_value(value)
        allowed_by_norm = {cls._norm_dict_value(item): item for item in allowed_values}
        if source in allowed_by_norm:
            return allowed_by_norm[source]

        if alias == "season":
            for synonym in cls._season_synonyms(source):
                if synonym in allowed_by_norm:
                    return allowed_by_norm[synonym]
        return None

    @staticmethod
    def _norm_dict_value(value: Any) -> str:
        text = str(value or "").casefold().replace("ё", "е")
        return "".join(char for char in text if char.isalnum())

    @staticmethod
    def _season_synonyms(value: str) -> list[str]:
        if value in {"всесезонный", "всесезонная", "всесезонное", "круглыйгод", "allseason", "yearround"}:
            return ["круглогодичный"]
        if value in {"летний", "летняя", "summer"}:
            return ["лето"]
        if value in {"зимний", "зимняя", "winter"}:
            return ["зима"]
        if value in {"демисезонный", "демисезонная", "межсезонье", "springautumn", "осеньвесна"}:
            return ["демисезон"]
        return []

    @staticmethod
    def _iter_variants(payload: Any):
        if isinstance(payload, list):
            for group in payload:
                if isinstance(group, dict):
                    yield from group.get("variants") or []
        elif isinstance(payload, dict):
            yield from payload.get("cardsToAdd") or payload.get("variants") or []

    def _upsert(self, variant: dict[str, Any], charc_id: int, value: Any, *, overwrite: bool = True) -> None:
        value = self._limit_value(charc_id, value)
        characteristics = variant.setdefault("characteristics", [])
        for item in characteristics:
            if isinstance(item, dict) and item.get("id") == charc_id:
                if not overwrite and item.get("value"):
                    return
                item["value"] = value
                return
        characteristics.append({"id": charc_id, "value": value})

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, (int, float)):
            return value
        text = str(value or "").strip()
        if not text:
            return []
        if ";" in text:
            return [part.strip() for part in text.split(";") if part.strip()]
        return [text]

    @staticmethod
    def _norm_name(value: Any) -> str:
        return str(value or "").casefold().replace(" ", "").replace("-", "")

    @staticmethod
    def _first(attrs: dict[str, Any], names: list[str]) -> Any:
        for name in names:
            if attrs.get(name):
                return attrs[name]
        return None

    @staticmethod
    def _fit_value(fit_type: str | None, text: str) -> str | None:
        source = f"{fit_type or ''} {text}".casefold()
        if "высок" in source:
            return "высокая"
        if "сред" in source:
            return "средняя"
        if "низк" in source:
            return "низкая"
        return fit_type

    @staticmethod
    def _pants_model(text: str) -> str | None:
        if "шир" in text or "wide" in text:
            return "широкие"
        if "прям" in text:
            return "прямые"
        if "зауж" in text:
            return "зауженные"
        return None

    @staticmethod
    def _closure(text: str, *, subject_id: int | None = None) -> str | None:
        values = []
        if "молни" in text:
            values.append("молния")
        if "пугов" in text:
            values.append("пуговицы")
        if "резин" in text:
            values.append("резинка")
        if not values and subject_id == 11:
            values.append("молния")
        return "; ".join(values) if values else None

    @staticmethod
    def _pockets(text: str) -> str | None:
        if "боков" in text and "карман" in text:
            return "боковые"
        if "наклад" in text and "карман" in text:
            return "накладные"
        if "карман" in text:
            return "в шве"
        return None

    @staticmethod
    def _features(features: list[str]) -> str | None:
        cleaned = [item for item in features if item]
        return "; ".join(cleaned[:5]) if cleaned else None

    @staticmethod
    def _default_purpose(text: str) -> str:
        if any(token in text for token in ["бель", "трус", "боксер"]):
            return "повседневная; в школу; для спорта"
        if any(token in text for token in ["сумк", "рюкзак", "кошел"]):
            return "повседневная; в школу; в поездки"
        if any(token in text for token in ["пижам", "сорочка", "халат"]):
            return "для сна; домашняя; для отдыха"
        return "повседневная; для прогулок; учеба"

    @staticmethod
    def _care_value(text: str) -> str:
        if "шерст" in text:
            return "деликатная стирка; не отбеливать; сушить в расправленном виде"
        if "кож" in text:
            return "не стирать; чистка влажной салфеткой; не отбеливать"
        return "бережная стирка; не отбеливать; гладить при низкой температуре"

    @staticmethod
    def _pattern_value(text: str, *, subject_id: int | None = None) -> str:
        if "полоск" in text:
            return "полоска"
        if "клет" in text:
            return "клетка"
        if "принт" in text or "рисун" in text:
            return "принт"
        if subject_id == 11:
            return "без рисунка"
        return "без рисунка"

    @staticmethod
    def _texture_value(attrs: dict[str, Any], analysis: ImageAnalysis | None, text: str) -> str:
        material = " ".join(
            str(item or "")
            for item in [attrs.get("Состав"), analysis.material if analysis else None, text]
        ).casefold()
        if "джинс" in material or "деним" in material:
            return "джинсовая"
        if "трикот" in material or "хлоп" in material:
            return "трикотажная"
        if "вельвет" in material:
            return "вельветовая"
        if "кож" in material:
            return "кожаная"
        return "гладкая"

    @staticmethod
    def _decor_value(text: str) -> str | None:
        values = []
        if "шнур" in text:
            values.append("шнурок")
        if "молни" in text:
            values.append("молния")
        if "пугов" in text:
            values.append("пуговицы")
        return "; ".join(values[:3]) if values else None

    @staticmethod
    def _neckline_value(text: str) -> str | None:
        if "v-" in text or "v образ" in text:
            return "V-образный"
        if "круг" in text:
            return "круглый"
        return None

    @staticmethod
    def _sleeve_value(text: str) -> str | None:
        if "длин" in text and "рукав" in text:
            return "длинный рукав"
        if "корот" in text and "рукав" in text:
            return "короткий рукав"
        return None

    @staticmethod
    def _contents(subject_id: int) -> str:
        if subject_id == 11:
            return "Брюки - 1 шт."
        return "Товар - 1 шт."

    @staticmethod
    def _is_confirmed(
        alias: str,
        value: Any,
        *,
        user_input: ProductInput | None,
        analysis: ImageAnalysis | None,
        user_attrs: dict[str, Any],
        seo_inputs: Any,
    ) -> bool:
        alias_to_sources = {
            "composition": [user_attrs.get("Состав"), getattr(seo_inputs, "material", None), analysis.material if analysis else None],
            "color": [user_attrs.get("Цвет"), getattr(seo_inputs, "color", None), user_input.color if user_input else None],
            "gender": [user_attrs.get("Пол"), getattr(seo_inputs, "target_audience", None), user_input.gender if user_input else None],
            "season": [user_attrs.get("Сезон"), getattr(seo_inputs, "season", None)],
            "fit": [user_attrs.get("Тип посадки"), getattr(seo_inputs, "fit", None)],
            "purpose": [user_attrs.get("Назначение"), getattr(seo_inputs, "purpose", None), user_input.note if user_input else None],
            "pattern": [user_attrs.get("Рисунок"), getattr(seo_inputs, "pattern", None)],
        }
        for source in alias_to_sources.get(alias, []):
            if source is None:
                continue
            text = str(source).strip().casefold()
            if text and str(value).strip().casefold() in text:
                return True
        return alias not in HIGH_RISK_ALIASES
