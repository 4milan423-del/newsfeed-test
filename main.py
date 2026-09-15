#!/usr/bin/env python3
"""Oikeustapausseuranta: hakee ratkaisut, suodattaa ne ja kirjoittaa sivun.

Käyttö:
    python main.py                  # normaali ajo
    python main.py --only kko,kho   # vain tietyt lähteet
    python main.py --dry-run        # ei kirjoita tiedostoja, tulostaa osumat
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from fetchers import Item, fetch_source
from filtering import filter_items
from render import write_all

ROOT = Path(__file__).parent
OUT = ROOT / "docs"
STATE = ROOT / "state.json"


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_state() -> set[str]:
    if not STATE.exists():
        return set()
    try:
        return set(json.loads(STATE.read_text(encoding="utf-8")).get("seen", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_state(keys: set[str]) -> None:
    # Pidetään muistissa 4000 viimeisintä avainta, jotta tiedosto ei kasva rajatta.
    STATE.write_text(
        json.dumps({"seen": sorted(keys)[-4000:]}, ensure_ascii=False, indent=0),
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "sources.yaml"))
    ap.add_argument("--only", help="pilkulla eroteltu lista lähteiden id-tunnuksia")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--base-url", default="", help="julkaisuosoite RSS-syötteeseen")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(message)s",
    )
    log = logging.getLogger("oikeusfeed")

    cfg = load_config(Path(args.config))
    settings = cfg.get("settings", {})
    sources = cfg.get("sources", [])

    if args.only:
        wanted = {s.strip() for s in args.only.split(",")}
        sources = [s for s in sources if s["id"] in wanted]
        if not sources:
            log.error("Yksikään lähde ei vastaa valintaa %s", args.only)
            return 1

    log.info("Haetaan %d lähdettä", len(sources))
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(fetch_source, sources))

    raw: list[Item] = [item for batch in results for item in batch]
    log.info("Yhteensä %d juttua ennen suodatusta", len(raw))

    items = filter_items(
        raw,
        cfg.get("keywords", {}),
        int(settings.get("window_days", 90)),
    )[: int(settings.get("max_items", 150))]

    seen = load_state()
    new_keys = {it.key for it in items} - seen

    if args.dry_run:
        for it in items:
            flag = "UUSI" if it.key in new_keys else "    "
            print(f"{flag} {it.date} {it.court:>6}  {it.title[:70]}")
            if it.keywords:
                print(f"            {it.keywords[:100]}")
        print(f"\n{len(items)} osumaa, {len(new_keys)} uutta. Tiedostoja ei kirjoitettu.")
        return 0

    write_all(
        items,
        settings,
        [s["name"] for s in sources],
        OUT,
        new_keys,
        base_url=args.base_url,
    )
    save_state(seen | {it.key for it in items})

    log.info("Kirjoitettu %s (%d juttua, %d uutta)", OUT / "index.html", len(items), len(new_keys))
    return 0


if __name__ == "__main__":
    sys.exit(main())
