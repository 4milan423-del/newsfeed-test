"""Lähdekohtaiset hakijat.

Jokainen hakija saa lähteen konfiguraation ja palauttaa listan Item-olioita.
Uuden lähdetyypin lisääminen: kirjoita funktio ja rekisteröi se FETCHERS-sanakirjaan.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import urllib.parse
from dataclasses import dataclass, field

import feedparser
import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

USER_AGENT = "oikeusfeed/1.0 (henkilokohtainen oikeustapausseuranta)"
TIMEOUT = 45

SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"


@dataclass
class Item:
    """Yksi ratkaisu feedissä."""

    source_id: str
    source_name: str
    court: str
    title: str
    url: str
    date: dt.date
    keywords: str = ""          # asiasanat, esim. "Tietosuoja – Rekisterinpitäjä"
    summary: str = ""           # vapaa tiivistelmä tai asianosaiset
    weight: int = 1             # lähteen painoarvo järjestyksessä
    score: int = 0              # täytetään suodatuksessa
    tags: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)  # täytetään suodatuksessa
    always: bool = False        # ohittaa avainsanasuodatuksen, ks. always_include

    @property
    def key(self) -> str:
        """Vakaa tunniste päällekkäisyyksien karsimiseen."""
        return self.url.split("?")[0].rstrip("/")

    def haystack(self) -> str:
        return " ".join([self.title, self.keywords, self.summary]).lower()

    def title_haystack(self) -> str:
        """Otsikko ja asiasanat ilman tiivistelmää.

        never-lista katsotaan tästä. Tiivistelmässä voi mainita ohimennen
        webinaarin tai vuosikertomuksen ilman että juttu itse on sellainen.
        Kyberturvallisuuskeskuksen viikkokatsaus 36/2026 putosi feedistä juuri
        näin, koska tiivistelmässä mainittiin CSIRT-ajankohtaiswebinaari.
        """
        return " ".join([self.title, self.keywords]).lower()


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def _parse_date(entry) -> dt.date:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            return dt.date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)
    return dt.date.today()


def _is_swedish_duplicate(title: str, url: str) -> bool:
    """Tuomioistuinten syötteissä sama ratkaisu tulee kahdesti, fi ja sv."""
    if "/sv/" in url or "/en/" in url:
        return True
    return bool(re.match(r"^(HD|HFD|MD|AD):", title.strip()))


# --------------------------------------------------------------------------
# Tuomioistuinlaitoksen WordPress-syötteet (KKO, KHO, MAO, TT, VakO, hovit)
# --------------------------------------------------------------------------
def fetch_wp_rss(source: dict) -> list[Item]:
    resp = _session().get(source["url"], timeout=TIMEOUT)
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)

    items: list[Item] = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        url = (entry.get("link") or "").strip()
        if not title or not url:
            continue
        if _is_swedish_duplicate(title, url):
            continue

        # Asiasanat tulevat <category>-elementeistä. Ne ovat suodatuksen
        # tärkein signaali, koska otsikko on pelkkä "KKO:2026:62".
        cats = [c.get("term", "") for c in entry.get("tags", []) or []]
        keywords = ", ".join(c for c in cats if c)

        items.append(
            Item(
                source_id=source["id"],
                source_name=source["name"],
                court=source.get("court", source["name"]),
                title=title,
                url=url,
                date=_parse_date(entry),
                keywords=keywords,
                weight=source.get("weight", 1),
            )
        )
    return items


# --------------------------------------------------------------------------
# Tavallinen RSS tai Atom (EDPB, CURIA, mikä tahansa muu syöte)
# --------------------------------------------------------------------------
def fetch_plain_rss(source: dict) -> list[Item]:
    resp = _session().get(source["url"], timeout=TIMEOUT)
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)

    items: list[Item] = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        url = (entry.get("link") or "").strip()
        if not title or not url:
            continue

        raw = entry.get("summary") or entry.get("description") or ""
        summary = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
        # EDPB toistaa otsikon kuvauksessa. Karsitaan toisto pois.
        summary = summary.replace(title, "").strip()

        items.append(
            Item(
                source_id=source["id"],
                source_name=source["name"],
                court=source.get("court", source["name"]),
                title=title,
                url=url,
                date=_parse_date(entry),
                summary=summary[:400],
                weight=source.get("weight", 1),
            )
        )
    return items


# --------------------------------------------------------------------------
# Unionin tuomioistuin Cellarin SPARQL-rajapinnasta
# --------------------------------------------------------------------------
SPARQL_TEMPLATE = """
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX lang: <http://publications.europa.eu/resource/authority/language/>
SELECT DISTINCT ?celex ?date ?ecli ?lg ?parties ?subject WHERE {{
  ?work cdm:resource_legal_id_celex ?celex ;
        cdm:work_date_document ?date .
  FILTER({celex_filter})
  FILTER(?date >= "{since}"^^<http://www.w3.org/2001/XMLSchema#date>)
  OPTIONAL {{ ?work cdm:case-law_ecli ?ecli }}
  OPTIONAL {{
    # Suomenkielinen toisinto ei ole heti saatavilla kaikista ratkaisuista,
    # joten englanti otetaan varalle ja suomi voittaa jos molemmat löytyvät.
    VALUES ?lg {{ lang:{lang} lang:ENG }}
    ?expr cdm:expression_belongs_to_work ?work ;
          cdm:expression_uses_language ?lg .
    OPTIONAL {{ ?expr cdm:expression_case-law_parties ?parties }}
    OPTIONAL {{ ?expr cdm:expression_case-law_indicator_decision ?subject }}
  }}
}}
ORDER BY DESC(?date)
LIMIT 800
"""


def fetch_eu_sparql(source: dict) -> list[Item]:
    lookback = int(source.get("lookback_days", 120))
    since = (dt.date.today() - dt.timedelta(days=lookback)).isoformat()
    lang = source.get("language", "fin").upper()
    years = {dt.date.today().year, dt.date.today().year - 1, dt.date.today().year - 2}
    types = source.get("celex_types", ["CJ", "TJ"])

    prefixes = [f"6{y}{t}" for y in sorted(years) for t in types]
    celex_filter = " || ".join(
        f'STRSTARTS(STR(?celex), "{p}")' for p in prefixes
    )

    query = SPARQL_TEMPLATE.format(
        celex_filter=celex_filter, since=since, lang=lang
    )
    resp = _session().get(
        SPARQL_ENDPOINT,
        params={"query": query, "format": "application/sparql-results+json"},
        timeout=180,
    )
    resp.raise_for_status()
    bindings = resp.json()["results"]["bindings"]

    # Sama celex tulee useana rivinä, yksi per kieli ja per asiasanajoukko.
    # Valitaan suomenkielinen rivi ja niistä pisin asiasanajono.
    best: dict[str, dict] = {}
    for b in bindings:
        celex = b["celex"]["value"]
        is_fin = b.get("lg", {}).get("value", "").endswith(f"/{lang}")
        row = {
            "date": b["date"]["value"],
            "ecli": b.get("ecli", {}).get("value", ""),
            "parties": b.get("parties", {}).get("value", ""),
            "subject": b.get("subject", {}).get("value", ""),
            "fin": is_fin,
        }
        prev = best.get(celex)
        if prev is None:
            best[celex] = row
            continue
        better_lang = row["fin"] and not prev["fin"]
        same_lang_longer = row["fin"] == prev["fin"] and len(row["subject"]) > len(prev["subject"])
        if better_lang or same_lang_longer:
            best[celex] = row

    items: list[Item] = []
    for celex, row in best.items():
        case_no = _celex_to_case_number(celex)
        kind = {"CJ": "tuomio", "TJ": "tuomio (unionin yleinen tuomioistuin)",
                "CC": "julkisasiamiehen ratkaisuehdotus",
                "CO": "määräys"}.get(celex[5:7], "ratkaisu")
        title = f"{case_no}, {kind}"
        if row["parties"]:
            title = f"{case_no} {row['parties'][:110]} ({kind})"

        items.append(
            Item(
                source_id=source["id"],
                source_name=source["name"],
                court=source.get("court", "EUT"),
                title=title,
                url=f"https://eur-lex.europa.eu/legal-content/FI/TXT/?uri=CELEX:{celex}",
                date=dt.date.fromisoformat(row["date"]),
                keywords=row["subject"][:600],
                summary=row["ecli"],
                weight=source.get("weight", 1),
            )
        )
    return items


def _celex_to_case_number(celex: str) -> str:
    """62024CJ0669 -> C-669/24. Yleisen tuomioistuimen asiat saavat T-tunnuksen."""
    m = re.match(r"^6(\d{4})(CJ|TJ|CC|CO)(\d{4})", celex)
    if not m:
        return celex
    year, ctype, number = m.groups()
    letter = "T" if ctype == "TJ" else "C"
    return f"{letter}-{int(number)}/{year[2:]}"


# --------------------------------------------------------------------------
# Yleinen HTML-listaus (esim. tietosuojavaltuutetun ratkaisut)
# --------------------------------------------------------------------------
def fetch_html_list(source: dict) -> list[Item]:
    resp = _session().get(source["url"], timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    pattern = re.compile(source.get("link_pattern", ".")) if source.get("link_pattern") else None

    seen: set[str] = set()
    items: list[Item] = []
    for a in soup.find_all("a", href=True):
        # Osa sivustoista (ENISA) jättää href-arvoon välilyöntejä.
        href = urllib.parse.urljoin(source["url"], a["href"].strip())
        text = a.get_text(" ", strip=True)
        if len(text) < 20 or href in seen:
            continue
        if pattern and not pattern.search(href):
            continue
        seen.add(href)

        # Etsitään päivämäärä linkin läheltä. Jos ei löydy, käytetään tätä päivää
        # ja merkitään se epävarmaksi tagilla.
        date, exact = _guess_date(a), True
        if date is None:
            date, exact = dt.date.today(), False

        items.append(
            Item(
                source_id=source["id"],
                source_name=source["name"],
                court=source.get("court", source["name"]),
                title=text[:200],
                url=href,
                date=date,
                weight=source.get("weight", 1),
                tags=[] if exact else ["pvm arvioitu"],
            )
        )
    return items


DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")


def _guess_date(anchor) -> dt.date | None:
    node = anchor
    for _ in range(4):
        if node is None:
            break
        time_el = node.find("time") if hasattr(node, "find") else None
        if time_el and time_el.get("datetime"):
            try:
                return dt.date.fromisoformat(time_el["datetime"][:10])
            except ValueError:
                pass
        m = DATE_RE.search(node.get_text(" ", strip=True)) if hasattr(node, "get_text") else None
        if m:
            d, mo, y = (int(x) for x in m.groups())
            try:
                return dt.date(y, mo, d)
            except ValueError:
                pass
        node = node.parent
    return None


# --------------------------------------------------------------------------
# OAI-PMH: yliopistojen julkaisuarkistot (väitöskirjat, gradut)
# --------------------------------------------------------------------------
# DSpace-arkistot puhuvat OAI-PMH:ta. ListRecords palauttaa 100 tietuetta
# kerrallaan ja antaa resumptionTokenin seuraavaa sivua varten. Tietueet
# tulevat datestamp-järjestyksessä vanhimmasta uusimpaan, joten haku pitää
# aloittaa tarpeeksi läheltä nykyhetkeä eikä sivuja kannata hakea rajatta.
def fetch_oai_pmh(source: dict) -> list[Item]:
    lookback = int(source.get("lookback_days", 75))
    since = (dt.date.today() - dt.timedelta(days=lookback)).isoformat()
    max_pages = int(source.get("max_pages", 6))

    sess = _session()
    params = {"verb": "ListRecords", "metadataPrefix": "oai_dc", "from": since}
    if source.get("oai_set"):
        params["set"] = source["oai_set"]

    items: list[Item] = []
    for _ in range(max_pages):
        resp = sess.get(source["url"], params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "xml")

        error = soup.find("error")
        if error is not None:
            # noRecordsMatch on normaali tilanne, ei virhe.
            if error.get("code") != "noRecordsMatch":
                log.warning("%s OAI-virhe: %s", source["id"], error.get("code"))
            break

        for record in soup.find_all("record"):
            item = _oai_item(record, source)
            if item is not None:
                items.append(item)

        token = soup.find("resumptionToken")
        value = token.get_text(strip=True) if token else ""
        if not value:
            break
        params = {"verb": "ListRecords", "resumptionToken": value}

    return items


def _oai_item(record, source: dict) -> Item | None:
    meta = record.find("metadata")
    if meta is None:
        return None

    def values(tag: str) -> list[str]:
        return [e.get_text(" ", strip=True) for e in meta.find_all(tag)]

    titles = values("dc:title")
    if not titles:
        return None

    # Handle-osoite on pysyvä, muut identifierit voivat olla tiedostopolkuja.
    ids = values("dc:identifier")
    url = next((i for i in ids if i.startswith("http") and "handle" in i), "")
    url = url or next((i for i in ids if i.startswith("http")), "")
    if not url:
        return None

    # Julkaisupäivä on dc:date. Jos se ei jäsenny, käytetään tietueen
    # muokkausaikaa headerista.
    header = record.find("header")
    stamp = header.find("datestamp").get_text(strip=True) if header and header.find("datestamp") else ""
    date = None
    for candidate in values("dc:date") + [stamp]:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", candidate)
        if m:
            parsed = dt.date(int(m[1]), int(m[2]), int(m[3]))
            if parsed <= dt.date.today():
                date = parsed
                break
    if date is None:
        return None

    # Tyyppirajaus pudottaa arkistojen muun aineiston (kuvat, aineistot) pois.
    wanted = [t.lower() for t in source.get("type_contains") or []]
    if wanted:
        types = " ".join(values("dc:type")).lower()
        if not any(w in types for w in wanted):
            return None

    return Item(
        source_id=source["id"],
        source_name=source["name"],
        court=source.get("court", source["name"]),
        title=titles[0][:220],
        url=url,
        date=date,
        keywords=", ".join(values("dc:subject"))[:300],
        summary=" ".join(values("dc:description"))[:400],
        weight=source.get("weight", 1),
    )


FETCHERS = {
    "wp_rss": fetch_wp_rss,
    "plain_rss": fetch_plain_rss,
    "eu_sparql": fetch_eu_sparql,
    "html_list": fetch_html_list,
    "oai_pmh": fetch_oai_pmh,
}


@dataclass
class SourceResult:
    """Yhden lähteen ajon lopputulos.

    Tätä tarvitaan sivun lähdepaneeliin. Pelkkä juttulista ei riitä, koska
    nolla juttua voi tarkoittaa kahta eri asiaa: lähde vastasi eikä sillä
    ollut mitään uutta, tai lähde ei vastannut lainkaan. Nämä pitää erottaa
    toisistaan, jotta sivulla voi luvata että se kertoo mitä ei ole katettu.
    """

    source_id: str
    name: str
    court: str
    items: list[Item] = field(default_factory=list)
    ok: bool = True
    optional: bool = False
    error: str = ""


def fetch_source(source: dict) -> SourceResult:
    """Hakee yhden lähteen. Virhe ei kaada koko ajoa."""
    result = SourceResult(
        source_id=source["id"],
        name=source.get("name", source["id"]),
        court=source.get("court", source["id"]),
        optional=bool(source.get("optional")),
    )

    fetcher = FETCHERS.get(source["type"])
    if fetcher is None:
        log.warning("Tuntematon lähdetyyppi %r lähteessä %s", source["type"], source["id"])
        result.ok = False
        result.error = f"tuntematon lähdetyyppi {source['type']}"
        return result
    try:
        items = fetcher(source)

        # Lähdekohtainen lisäehto. Julkaisuarkistot sisältävät kaiken alan
        # tutkimuksen, joten niistä otetaan vain oikeustieteellinen aineisto.
        # Tämä on eri asia kuin sources.yaml:n aihekohtainen must_any.
        require = [t.lower() for t in source.get("require_any") or []]
        if require:
            items = [i for i in items if any(t in i.haystack() for t in require)]

        # Lähdekohtainen poissulku. Globaali never-lista ei sovi tähän, koska
        # sama sana voi olla toisessa lähteessä juuri se mitä haetaan.
        # Esimerkki: "kriittinen haavoittuvuus" on Kyberturvallisuuskeskuksen
        # tuotetiedotteissa pelkkää kohinaa, mutta sama sana komission
        # tiedotteessa koskee kyberkestävyyssäädöstä.
        block = [t.lower() for t in source.get("never_any") or []]
        if block:
            items = [i for i in items
                     if not any(t in i.title_haystack() for t in block)]

        if source.get("always_include"):
            for item in items:
                item.always = True
        log.info("%-12s %3d juttua", source["id"], len(items))
        result.items = items
        return result
    except Exception as exc:  # noqa: BLE001
        level = logging.WARNING if source.get("optional") else logging.ERROR
        log.log(level, "%-12s epäonnistui: %s", source["id"], exc)
        result.ok = False
        result.error = str(exc)[:200]
        return result
