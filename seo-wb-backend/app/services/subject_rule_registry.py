from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SubjectRule:
    subject_code: str
    ru_names: tuple[str, ...]
    family: str
    title_patterns: tuple[tuple[str, ...], ...]
    description_blueprint: dict[str, str]
    critical_attributes: tuple[str, ...]
    forbidden_terms: tuple[str, ...] = ()
    semantic_conflicts: dict[str, tuple[str, ...]] = field(default_factory=dict)
    attribute_inference_rules: dict[str, Any] = field(default_factory=dict)
    seo_priority: tuple[str, ...] = ()


class SubjectRuleRegistry:
    _RULES: tuple[SubjectRule, ...] = (
        SubjectRule(
            subject_code="jeans",
            ru_names=("джинсы",),
            family="bottoms",
            title_patterns=(("subject", "model", "rise_phrase", "decor"),),
            description_blueprint={
                "opening": "{subject_label_cap} из {material} подходят для повседневного гардероба и выглядят актуально без перегруженного декора.",
                "fit": "{fit_sentence} {rise_sentence}",
                "material": "Плотная ткань {material} приятно ощущается в носке и помогает модели сохранять аккуратную форму.",
                "use_case": "Такие {subject_label} легко вписываются в сценарии {use_cases} и сочетаются с базовыми футболками, топами и худи.",
                "care": "Уход: бережная стирка при 30 градусах, не отбеливать, гладить при низкой температуре.",
            },
            critical_attributes=("Модель джинсов", "Тип посадки", "Вид застежки", "Декоративные элементы", "Состав"),
            semantic_conflicts={
                "cross_subject": ("брюки", "юбка", "платье", "леггинсы"),
                "materials": ("лен", "трикотаж"),
            },
            attribute_inference_rules={"closure_default": "молния", "pattern_default": "без рисунка"},
            seo_priority=("fit", "rise", "decor", "material"),
        ),
        SubjectRule(
            subject_code="trousers",
            ru_names=("брюки",),
            family="bottoms",
            title_patterns=(("subject", "fit", "rise_phrase", "detail"),),
            description_blueprint={
                "opening": "{subject_label_cap} из {material} подходят для повседневной носки и создают аккуратный силуэт.",
                "fit": "{fit_sentence} {rise_sentence}",
                "material": "{color_sentence} Материал {material} комфортен в движении и подходит для длительной носки.",
                "use_case": "Эти {subject_label} уместны для сценариев {use_cases} и легко сочетаются с рубашками, футболками и жакетами.",
                "care": "Уход: деликатная стирка и бережное хранение помогают сохранить форму и внешний вид модели.",
            },
            critical_attributes=("Модель брюк", "Тип посадки", "Вид застежки", "Состав"),
            semantic_conflicts={
                "cross_subject": ("джинсы", "юбка", "платье"),
                "materials": ("деним",),
            },
            attribute_inference_rules={"closure_default": "молния", "pattern_default": "без рисунка"},
            seo_priority=("fit", "material", "color", "season"),
        ),
        SubjectRule(
            subject_code="leggings",
            ru_names=("леггинсы",),
            family="bottoms",
            title_patterns=(("subject", "fit", "purpose"),),
            description_blueprint={
                "opening": "{subject_label_cap} созданы для комфорта и плотной посадки без лишних деталей.",
                "fit": "{fit_sentence}",
                "material": "Материал {material} помогает сохранить удобство в движении и мягко прилегает к телу.",
                "use_case": "Модель подходит для сценариев {use_cases} и хорошо работает как для прогулок, так и для активного дня.",
                "care": "Уход: стирать на деликатном режиме, избегать агрессивного отбеливания.",
            },
            critical_attributes=("Состав", "Покрой", "Назначение"),
            semantic_conflicts={"cross_subject": ("джинсы", "юбка", "платье")},
            seo_priority=("fit", "material", "purpose"),
        ),
        SubjectRule(
            subject_code="skirt",
            ru_names=("юбка",),
            family="dresses_skirts",
            title_patterns=(("subject", "length", "silhouette", "detail"),),
            description_blueprint={
                "opening": "{subject_label_cap} помогает собрать аккуратный и женственный образ на каждый день.",
                "fit": "{fit_sentence} {length_sentence}",
                "material": "{color_sentence} Материал {material} выглядит уместно и комфортно ощущается в носке.",
                "use_case": "Модель подходит для сценариев {use_cases} и легко комбинируется с футболками, блузками и кардиганами.",
                "care": "Уход: деликатная стирка и аккуратная сушка помогают сохранить форму изделия.",
            },
            critical_attributes=("Длина изделия", "Фасон", "Состав", "Сезон"),
            semantic_conflicts={"cross_subject": ("платье", "джинсы", "брюки")},
            seo_priority=("length", "silhouette", "material", "color"),
        ),
        SubjectRule(
            subject_code="dress",
            ru_names=("платье",),
            family="dresses_skirts",
            title_patterns=(("subject", "length", "style", "detail"),),
            description_blueprint={
                "opening": "{subject_label_cap} создает цельный образ и помогает выглядеть аккуратно в течение дня.",
                "fit": "{fit_sentence} {length_sentence}",
                "material": "{color_sentence} Материал {material} приятен к телу и поддерживает комфортную посадку.",
                "use_case": "Платье подходит для сценариев {use_cases} и сочетается с базовой обувью и легким верхним слоем.",
                "care": "Уход: бережная стирка и сушка в расправленном виде помогают сохранить внешний вид модели.",
            },
            critical_attributes=("Длина изделия", "Фасон", "Вырез горловины", "Сезон", "Состав"),
            semantic_conflicts={"cross_subject": ("юбка", "джинсы", "брюки")},
            seo_priority=("length", "style", "season", "material"),
        ),
        SubjectRule(
            subject_code="tshirt",
            ru_names=("футболка",),
            family="tops",
            title_patterns=(("subject", "fit", "detail"),),
            description_blueprint={
                "opening": "{subject_label_cap} остается универсальной базой для повседневного гардероба.",
                "fit": "{fit_sentence}",
                "material": "{color_sentence} Материал {material} приятен к телу и подходит для ежедневной носки.",
                "use_case": "Модель уместна для сценариев {use_cases} и легко сочетается с джинсами, брюками и юбками.",
                "care": "Уход: машинная стирка на щадящем режиме помогает сохранить форму и аккуратный внешний вид.",
            },
            critical_attributes=("Состав", "Вырез горловины", "Тип рукава", "Покрой"),
            semantic_conflicts={"cross_subject": ("рубашка", "худи", "свитшот")},
            seo_priority=("fit", "material", "detail"),
        ),
        SubjectRule(
            subject_code="shirt",
            ru_names=("рубашка",),
            family="tops",
            title_patterns=(("subject", "fit", "detail"),),
            description_blueprint={
                "opening": "{subject_label_cap} помогает собрать аккуратный образ и остается практичной в повседневной носке.",
                "fit": "{fit_sentence}",
                "material": "{color_sentence} Материал {material} поддерживает комфорт и аккуратный внешний вид.",
                "use_case": "Рубашка подходит для сценариев {use_cases} и сочетается с брюками, джинсами и юбками.",
                "care": "Уход: стирать на деликатном режиме и сушить в расправленном виде.",
            },
            critical_attributes=("Состав", "Тип рукава", "Покрой"),
            semantic_conflicts={"cross_subject": ("футболка", "худи", "свитшот")},
            seo_priority=("fit", "material", "color"),
        ),
        SubjectRule(
            subject_code="hoodie",
            ru_names=("худи",),
            family="tops",
            title_patterns=(("subject", "fit", "hood_phrase", "detail"),),
            description_blueprint={
                "opening": "{subject_label_cap} подходит для расслабленного повседневного образа и комфортной носки.",
                "fit": "{fit_sentence}",
                "material": "{color_sentence} Материал {material} помогает сохранить мягкость и уют в течение дня.",
                "use_case": "Модель уместна для сценариев {use_cases} и хорошо сочетается с джинсами, брюками и шортами.",
                "care": "Уход: стирать при умеренной температуре, избегать агрессивной сушки.",
            },
            critical_attributes=("Состав", "Покрой", "Тип карманов"),
            semantic_conflicts={"cross_subject": ("свитшот", "рубашка", "футболка")},
            seo_priority=("fit", "material", "detail"),
        ),
        SubjectRule(
            subject_code="sweatshirt",
            ru_names=("свитшот",),
            family="tops",
            title_patterns=(("subject", "fit", "detail"),),
            description_blueprint={
                "opening": "{subject_label_cap} помогает собрать удобный повседневный образ без лишнего декора.",
                "fit": "{fit_sentence}",
                "material": "{color_sentence} Материал {material} ощущается комфортно и подходит для прохладной погоды.",
                "use_case": "Модель подходит для сценариев {use_cases} и легко сочетается с джинсами, брюками и спортивным низом.",
                "care": "Уход: бережная стирка помогает сохранить форму и аккуратный внешний вид изделия.",
            },
            critical_attributes=("Состав", "Покрой"),
            semantic_conflicts={"cross_subject": ("худи", "рубашка", "футболка")},
            seo_priority=("fit", "material", "detail"),
        ),
        SubjectRule(
            subject_code="jacket",
            ru_names=("куртка",),
            family="outerwear",
            title_patterns=(("subject", "fit", "detail"),),
            description_blueprint={
                "opening": "{subject_label_cap} подходит для прохладной погоды и помогает собрать практичный городской образ.",
                "fit": "{fit_sentence}",
                "material": "{color_sentence} Материал {material} поддерживает комфорт и защиту в повседневной носке.",
                "use_case": "Куртка уместна для сценариев {use_cases} и хорошо сочетается с базовыми вещами гардероба.",
                "care": "Уход: соблюдать рекомендации по стирке и сушке, чтобы сохранить форму и свойства ткани.",
            },
            critical_attributes=("Состав", "Сезон", "Тип застежки"),
            semantic_conflicts={"cross_subject": ("пальто", "худи", "рубашка")},
            seo_priority=("season", "material", "detail"),
        ),
        SubjectRule(
            subject_code="coat",
            ru_names=("пальто",),
            family="outerwear",
            title_patterns=(("subject", "fit", "length", "detail"),),
            description_blueprint={
                "opening": "{subject_label_cap} помогает собрать аккуратный верхний слой для прохладного сезона.",
                "fit": "{fit_sentence}",
                "material": "{color_sentence} Материал {material} выглядит уместно и поддерживает комфортную носку.",
                "use_case": "Пальто подходит для сценариев {use_cases} и сочетается с платьями, брюками и трикотажем.",
                "care": "Уход: следуйте рекомендациям на ярлыке, чтобы сохранить форму и внешний вид изделия.",
            },
            critical_attributes=("Состав", "Сезон", "Тип застежки"),
            semantic_conflicts={"cross_subject": ("куртка", "худи", "рубашка")},
            seo_priority=("season", "material", "color"),
        ),
        SubjectRule(
            subject_code="bra",
            ru_names=("бюстгальтер",),
            family="underwear",
            title_patterns=(("subject", "bra_type", "wire_state", "effect"),),
            description_blueprint={
                "opening": "{subject_label_cap} создан для комфортной поддержки и аккуратной посадки в течение дня.",
                "fit": "{fit_sentence}",
                "material": "Материал {material} мягко прилегает к телу и помогает сохранять ощущение комфорта.",
                "use_case": "Модель подходит для ежедневной носки и хорошо работает под разными типами одежды.",
                "care": "Уход: рекомендуется деликатная стирка, чтобы сохранить форму чашек и эластичность ткани.",
            },
            critical_attributes=("Тип бюстгальтера", "Наличие косточек", "Размер чашки", "Состав"),
            semantic_conflicts={"cross_subject": ("трусы", "пижама", "футболка")},
            seo_priority=("type", "support", "effect"),
        ),
        SubjectRule(
            subject_code="panties",
            ru_names=("трусы",),
            family="underwear",
            title_patterns=(("subject", "panties_type", "set_quantity"),),
            description_blueprint={
                "opening": "{subject_label_cap} рассчитаны на ежедневный комфорт и мягкую посадку.",
                "fit": "{fit_sentence}",
                "material": "Материал {material} приятен к телу и подходит для регулярной носки.",
                "use_case": "Модель удобна для повседневного использования и помогает поддерживать комфорт в течение дня.",
                "care": "Уход: деликатная стирка помогает сохранить мягкость ткани и форму изделия.",
            },
            critical_attributes=("Тип трусов", "Количество в наборе", "Состав", "Посадка"),
            semantic_conflicts={"cross_subject": ("бюстгальтер", "пижама", "футболка")},
            seo_priority=("type", "material", "quantity"),
        ),
        SubjectRule(
            subject_code="pajama",
            ru_names=("пижама",),
            family="sleepwear",
            title_patterns=(("subject", "detail", "purpose"),),
            description_blueprint={
                "opening": "{subject_label_cap} создана для отдыха, сна и мягкого домашнего комфорта.",
                "fit": "{fit_sentence}",
                "material": "Материал {material} приятен к телу и поддерживает комфорт во время отдыха.",
                "use_case": "Комплект подходит для сна, домашнего использования и спокойного отдыха.",
                "care": "Уход: бережная стирка помогает дольше сохранить мягкость и аккуратный вид ткани.",
            },
            critical_attributes=("Состав", "Комплектация", "Сезон"),
            semantic_conflicts={"cross_subject": ("бюстгальтер", "трусы", "футболка")},
            seo_priority=("material", "season", "detail"),
        ),
        SubjectRule(
            subject_code="shorts",
            ru_names=("шорты",),
            family="bottoms",
            title_patterns=(("subject", "fit", "detail", "purpose"),),
            description_blueprint={
                "opening": "{subject_label_cap} подходят для теплого сезона и повседневного активного дня.",
                "fit": "{fit_sentence}",
                "material": "{color_sentence} Материал {material} помогает сохранить комфорт и свободу движений.",
                "use_case": "Модель уместна для сценариев {use_cases} и хорошо сочетается с футболками, топами и худи.",
                "care": "Уход: деликатная стирка помогает сохранить форму и аккуратный внешний вид изделия.",
            },
            critical_attributes=("Состав", "Покрой", "Тип посадки"),
            semantic_conflicts={"cross_subject": ("брюки", "джинсы", "юбка")},
            seo_priority=("fit", "material", "season"),
        ),
    )

    @classmethod
    def resolve(cls, subject_name: str | None) -> SubjectRule | None:
        source = cls._norm(subject_name)
        if not source:
            return None
        for rule in cls._RULES:
            if any(name in source for name in rule.ru_names):
                return rule
        return None

    @classmethod
    def resolve_from_context(cls, *parts: str | None) -> SubjectRule | None:
        source = cls._norm(" ".join(str(part or "") for part in parts))
        if not source:
            return None
        for rule in cls._RULES:
            if any(name in source for name in rule.ru_names):
                return rule
        return None

    @classmethod
    def all_rules(cls) -> tuple[SubjectRule, ...]:
        return cls._RULES

    @staticmethod
    def _norm(value: str | None) -> str:
        return " ".join(str(value or "").casefold().split())
