"""HTML-sivun, RSS-syötteen ja JSON-datan kirjoitus."""

from __future__ import annotations

import datetime as dt
import html
import json
from email.utils import format_datetime
from pathlib import Path

from jinja2 import Template

from fetchers import Item

PAGE = Template("""<!doctype html>
<html lang="fi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title>
<link rel="alternate" type="application/rss+xml" title="{{ title }}" href="feed.xml">
<style>
  :root {
    --bg: #fbfaf8; --card: #ffffff; --ink: #1c1b19; --muted: #6b6862;
    --line: #e5e1da; --accent: #8a3324; --hot: #fdf3e7; --hotline: #e8c9a0;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#161513; --card:#1e1d1a; --ink:#ecebe7; --muted:#9a968e;
            --line:#2e2c28; --accent:#e0a080; --hot:#2a2118; --hotline:#5c4630; }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, system-ui, sans-serif; }
  .wrap { max-width: 820px; margin: 0 auto; padding: 32px 20px 80px; }
  header h1 { font-size: 1.6rem; margin: 0 0 4px; letter-spacing: -0.01em; }
  header p { margin: 0; color: var(--muted); font-size: 0.92rem; }
  .meta { margin-top: 14px; color: var(--muted); font-size: 0.82rem; }
  .controls { display:flex; gap:8px; flex-wrap:wrap; margin: 22px 0 6px; }
  input[type=search] { flex:1 1 240px; min-width:200px; padding:9px 12px;
    border:1px solid var(--line); border-radius:8px; background:var(--card); color:var(--ink); font-size:0.92rem; }
  .chip { padding:7px 12px; border:1px solid var(--line); border-radius:999px;
    background:var(--card); color:var(--muted); font-size:0.82rem; cursor:pointer; }
  .chip[aria-pressed=true] { background:var(--ink); color:var(--bg); border-color:var(--ink); }
  .daygroup { margin-top: 28px; }
  .daygroup > h2 { font-size:0.78rem; text-transform:uppercase; letter-spacing:0.07em;
    color:var(--muted); font-weight:600; margin:0 0 10px; }
  article { background:var(--card); border:1px solid var(--line); border-radius:10px;
    padding:14px 16px; margin-bottom:10px; }
  article.hot { background:var(--hot); border-color:var(--hotline); }
  article a.t { color:var(--ink); text-decoration:none; font-weight:600; font-size:1rem; }
  article a.t:hover { color:var(--accent); text-decoration:underline; }
  .court { display:inline-block; font-size:0.72rem; font-weight:700; letter-spacing:0.04em;
    color:var(--accent); margin-bottom:4px; }
  .kw { margin:6px 0 0; color:var(--muted); font-size:0.87rem; }
  .tags { margin-top:8px; display:flex; gap:6px; flex-wrap:wrap; }
  .tag { font-size:0.7rem; color:var(--muted); border:1px solid var(--line);
    padding:2px 7px; border-radius:999px; }
  .tag.new { color:var(--accent); border-color:var(--accent); font-weight:600; }
  footer { margin-top:48px; padding-top:18px; border-top:1px solid var(--line);
    color:var(--muted); font-size:0.8rem; }
  footer a { color:var(--muted); }
  .empty { color:var(--muted); padding:40px 0; }
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>{{ title }}</h1>
  <p>{{ subtitle }}</p>
  <div class="meta">
    Päivitetty {{ generated }} · {{ items|length }} ratkaisua · {{ new_count }} uutta
    · <a href="feed.xml">RSS</a> · <a href="data.json">JSON</a>
  </div>
</header>

<div class="controls">
  <input type="search" id="q" placeholder="Suodata otsikoista ja asiasanoista">
  {% for c in courts %}<button class="chip" data-court="{{ c }}" aria-pressed="false">{{ c }}</button>{% endfor %}
</div>

<main id="list">
{% for day, group in grouped %}
  <section class="daygroup">
    <h2>{{ day }}</h2>
    {% for it in group %}
    <article class="{% if 'tärkeä' in it.tags %}hot{% endif %}"
             data-court="{{ it.court }}"
             data-text="{{ (it.title ~ ' ' ~ it.keywords ~ ' ' ~ it.summary)|lower|e }}">
      <span class="court">{{ it.court }}</span>
      <div><a class="t" href="{{ it.url }}" target="_blank" rel="noopener">{{ it.title }}</a></div>
      {% if it.keywords %}<p class="kw">{{ it.keywords }}</p>{% endif %}
      {% if it.summary and not it.keywords %}<p class="kw">{{ it.summary }}</p>{% endif %}
      <div class="tags">
        {% if it.is_new %}<span class="tag new">uusi</span>{% endif %}
        {% for t in it.tags %}<span class="tag">{{ t }}</span>{% endfor %}
      </div>
    </article>
    {% endfor %}
  </section>
{% endfor %}
{% if not items %}<p class="empty">Ei osumia valitulla aikavälillä. Löysää avainsanoja sources.yaml-tiedostossa.</p>{% endif %}
</main>

<footer>
  Lähteet: {{ source_names|join(', ') }}.
  Seuranta on henkilökohtainen apuväline. Tarkista aina ratkaisu alkuperäisestä lähteestä
  ennen kuin nojaat siihen.
</footer>
</div>

<script>
const q = document.getElementById('q');
const chips = [...document.querySelectorAll('.chip')];
function apply() {
  const term = q.value.trim().toLowerCase();
  const active = chips.filter(c => c.getAttribute('aria-pressed') === 'true')
                      .map(c => c.dataset.court);
  document.querySelectorAll('article').forEach(a => {
    const okCourt = !active.length || active.includes(a.dataset.court);
    const okTerm = !term || a.dataset.text.includes(term);
    a.style.display = (okCourt && okTerm) ? '' : 'none';
  });
  document.querySelectorAll('.daygroup').forEach(s => {
    const any = [...s.querySelectorAll('article')].some(a => a.style.display !== 'none');
    s.style.display = any ? '' : 'none';
  });
}
q.addEventListener('input', apply);
chips.forEach(c => c.addEventListener('click', () => {
  c.setAttribute('aria-pressed', c.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
  apply();
}));
</script>
</body>
</html>
""")

FI_MONTHS = ["", "tammikuuta", "helmikuuta", "maaliskuuta", "huhtikuuta",
             "toukokuuta", "kesäkuuta", "heinäkuuta", "elokuuta",
             "syyskuuta", "lokakuuta", "marraskuuta", "joulukuuta"]


def fi_date(d: dt.date) -> str:
    return f"{d.day}. {FI_MONTHS[d.month]} {d.year}"


def write_all(items: list[Item], settings: dict, source_names: list[str],
              out_dir: Path, new_keys: set[str], base_url: str = "") -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    for it in items:
        it.is_new = it.key in new_keys  # type: ignore[attr-defined]

    grouped: list[tuple[str, list[Item]]] = []
    for it in items:
        label = fi_date(it.date)
        if grouped and grouped[-1][0] == label:
            grouped[-1][1].append(it)
        else:
            grouped.append((label, [it]))

    courts = sorted({it.court for it in items})
    now = dt.datetime.now()

    (out_dir / "index.html").write_text(
        PAGE.render(
            title=settings.get("site_title", "Oikeustapausseuranta"),
            subtitle=settings.get("site_subtitle", ""),
            generated=now.strftime("%-d.%-m.%Y klo %H:%M"),
            items=items,
            grouped=grouped,
            courts=courts,
            source_names=source_names,
            new_count=len(new_keys),
        ),
        encoding="utf-8",
    )

    _write_rss(items, settings, out_dir, base_url)

    (out_dir / "data.json").write_text(
        json.dumps(
            [
                {
                    "court": it.court,
                    "source": it.source_name,
                    "title": it.title,
                    "url": it.url,
                    "date": it.date.isoformat(),
                    "keywords": it.keywords,
                    "summary": it.summary,
                    "score": it.score,
                    "tags": it.tags,
                }
                for it in items
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_rss(items: list[Item], settings: dict, out_dir: Path, base_url: str) -> None:
    title = html.escape(settings.get("site_title", "Oikeustapausseuranta"))
    desc = html.escape(settings.get("site_subtitle", ""))
    link = base_url or "https://example.invalid/"

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"><channel>',
        f"<title>{title}</title>",
        f"<link>{html.escape(link)}</link>",
        f"<description>{desc}</description>",
        "<language>fi</language>",
        f"<lastBuildDate>{format_datetime(dt.datetime.now(dt.timezone.utc))}</lastBuildDate>",
    ]
    for it in items[:80]:
        body = it.keywords or it.summary
        pub = dt.datetime.combine(it.date, dt.time(9, 0), dt.timezone.utc)
        parts += [
            "<item>",
            f"<title>{html.escape(it.court + ': ' + it.title)}</title>",
            f"<link>{html.escape(it.url)}</link>",
            f"<guid isPermaLink=\"true\">{html.escape(it.url)}</guid>",
            f"<pubDate>{format_datetime(pub)}</pubDate>",
            f"<description>{html.escape(body)}</description>",
            "</item>",
        ]
    parts.append("</channel></rss>")
    (out_dir / "feed.xml").write_text("\n".join(parts), encoding="utf-8")
