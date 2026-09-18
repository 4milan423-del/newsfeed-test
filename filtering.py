"""Suodatus ja järjestäminen.

Logiikka on tarkoituksella yksinkertainen substring-haku. Se on riittävä,
koska tuomioistuinten asiasanat ovat vakiintuneita ja lyhyitä. Regexiin tai
embeddingeihin kannattaa siirtyä vasta jos väärät osumat alkavat häiritä.
"""

from __future__ import annotations

import datetime as dt
import logging

from fetchers import Item

log = logging.getLogger(__name__)


def matched_terms(haystack: str, terms: list[str]) -> list[str]:
    return [t for t in terms if t.lower() in haystack]


def assign_topics(item: Item, topics: dict[str, list[str]]) -> list[str]:
    """Antaa jutulle aiheluokat sources.yaml:n topics-lohkon perusteella.

    Sama juttu voi saada useita luokkia. Tietosuojavaltuutetun ratkaisu
    kasvojentunnistuksesta on sekä tietosuojaa että tekoälyä, ja sivulla se
    pitää löytyä kummankin napin takaa.
    """
    hay = item.haystack()
    return [name for name, terms in topics.items()
            if any(t.lower() in hay for t in terms or [])]


def filter_items(items: list[Item], keywords: dict, window_days: int,
                 topics: dict | None = None) -> list[Item]:
    must_any = [t for t in keywords.get("must_any") or []]
    boost = [t for t in keywords.get("boost") or []]
    never = [t for t in keywords.get("never") or []]

    cutoff = dt.date.today() - dt.timedelta(days=window_days)
    kept: list[Item] = []
    seen: set[str] = set()

    for item in items:
        if item.date < cutoff:
            continue
        if item.key in seen:
            continue

        hay = item.haystack()
        if matched_terms(item.title_haystack(), never):
            continue

        hits = matched_terms(hay, must_any) if must_any else ["*"]
        if not hits:
            # Osa lähteistä käsittelee vain tietosuojaa (tietosuojavaltuutettu,
            # EDPB). Niiden jutut otetaan mukaan, vaikka otsikko ei osuisi
            # yhteenkään avainsanaan. never-lista pätee silti.
            if not item.always:
                continue
            hits = ["*"]

        boosts = matched_terms(hay, boost)
        item.score = item.weight * 10 + len(hits) * 3 + len(boosts) * 12
        item.tags = list(item.tags)
        if boosts:
            item.tags.insert(0, "tärkeä")
        item.tags += [h for h in hits if h != "*"][:4]
        item.topics = assign_topics(item, topics or {})

        seen.add(item.key)
        kept.append(item)

    kept.sort(key=lambda i: (i.date, i.score), reverse=True)
    log.info("Suodatuksen jälkeen %d juttua", len(kept))
    return kept
