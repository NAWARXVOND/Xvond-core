from __future__ import annotations

from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

import pycountry


BUSINESS_TYPES = (
    "Catering / Events",
    "Salon / Beauty",
    "Restaurant / Cafe",
    "Retail Store",
    "E-commerce",
    "Clinic / Medical Center",
    "Dental Clinic",
    "Pharmacy",
    "Real Estate",
    "Hotel / Hospitality",
    "Travel / Tourism",
    "Professional Services",
    "Education / Training",
    "Gym / Fitness",
    "Automotive",
    "Home Services",
    "Maintenance / Contracting",
    "Logistics / Delivery",
    "Technology / Software",
    "Marketing / Media",
    "Financial / Accounting Services",
    "Legal Services",
    "Other",
)

BUSINESS_TYPE_ALIASES = {
    "catering": "Catering / Events",
    "event": "Catering / Events",
    "events": "Catering / Events",
    "catering / event": "Catering / Events",
    "catering / events": "Catering / Events",
    "restaurant": "Restaurant / Cafe",
    "cafe": "Restaurant / Cafe",
    "hospitality": "Hotel / Hospitality",
    "hotel": "Hotel / Hospitality",
    "clinic": "Clinic / Medical Center",
    "medical": "Clinic / Medical Center",
    "software": "Technology / Software",
    "technology": "Technology / Software",
}

COUNTRY_ALIASES = {
    "oman": "Oman",
    "عمان": "Oman",
    "عُمان": "Oman",
    "uae": "United Arab Emirates",
    "u.a.e.": "United Arab Emirates",
    "emirates": "United Arab Emirates",
    "syria": "Syrian Arab Republic",
    "syrian arab republic": "Syrian Arab Republic",
    "usa": "United States",
    "us": "United States",
    "uk": "United Kingdom",
}

LANGUAGE_ALIASES = {
    "arabic": "Arabic",
    "العربية": "Arabic",
    "عربي": "Arabic",
    "عربية": "Arabic",
    "english": "English",
    "انجليزي": "English",
    "إنجليزي": "English",
    "الإنجليزية": "English",
}


def _key(value: str | None) -> str:
    return " ".join(str(value or "").strip().split()).casefold()


@lru_cache(maxsize=1)
def _countries() -> tuple[str, ...]:
    return tuple(sorted({country.name for country in pycountry.countries}))


@lru_cache(maxsize=1)
def _currencies() -> tuple[str, ...]:
    return tuple(sorted({currency.alpha_3 for currency in pycountry.currencies}))


@lru_cache(maxsize=1)
def _languages() -> tuple[str, ...]:
    names = {
        language.name
        for language in pycountry.languages
        if getattr(language, "name", None)
        and (
            getattr(language, "alpha_2", None)
            or getattr(language, "alpha_3", None)
        )
    }
    return tuple(sorted(names))


@lru_cache(maxsize=1)
def _timezones() -> tuple[str, ...]:
    return tuple(sorted(available_timezones()))


@lru_cache(maxsize=1)
def _business_type_lookup() -> dict[str, str]:
    lookup = {_key(item): item for item in BUSINESS_TYPES}
    lookup.update({_key(k): v for k, v in BUSINESS_TYPE_ALIASES.items()})
    return lookup


@lru_cache(maxsize=1)
def _country_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for country in pycountry.countries:
        canonical = country.name
        for value in (
            getattr(country, "name", None),
            getattr(country, "official_name", None),
            getattr(country, "common_name", None),
            getattr(country, "alpha_2", None),
            getattr(country, "alpha_3", None),
        ):
            if value:
                lookup[_key(value)] = canonical
    lookup.update({_key(k): v for k, v in COUNTRY_ALIASES.items()})
    return lookup


@lru_cache(maxsize=1)
def _language_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for language in pycountry.languages:
        canonical = getattr(language, "name", None)
        if not canonical:
            continue
        for value in (
            canonical,
            getattr(language, "alpha_2", None),
            getattr(language, "alpha_3", None),
            getattr(language, "bibliographic", None),
        ):
            if value:
                lookup[_key(value)] = canonical
    lookup.update({_key(k): v for k, v in LANGUAGE_ALIASES.items()})
    return lookup


def normalize_business_type(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    result = _business_type_lookup().get(_key(value))
    if result is None:
        raise ValueError("Unsupported business type")
    return result


def normalize_country(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    result = _country_lookup().get(_key(value))
    if result is None:
        raise ValueError("Unsupported country")
    return result


def normalize_currency(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    code = str(value).strip().upper()
    if code not in _currencies():
        raise ValueError("Unsupported currency")
    return code


def normalize_timezone(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    zone = str(value).strip()
    try:
        ZoneInfo(zone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Unsupported timezone") from exc
    return zone


def normalize_language(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    result = _language_lookup().get(_key(value))
    if result is None:
        raise ValueError("Unsupported language")
    return result


def normalize_languages(values: list[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        normalized = normalize_language(value)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def company_catalog() -> dict:
    return {
        "business_types": list(BUSINESS_TYPES),
        "countries": list(_countries()),
        "currencies": list(_currencies()),
        "timezones": list(_timezones()),
        "languages": list(_languages()),
    }
