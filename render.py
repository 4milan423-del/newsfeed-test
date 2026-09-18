"""HTML-sivun, RSS-syötteen ja JSON-datan kirjoitus."""

from __future__ import annotations

import datetime as dt
import html
import json
from email.utils import format_datetime
from pathlib import Path

from jinja2 import Template

from fetchers import Item, SourceResult

PAGE = Template("""<!doctype html>
<html lang="fi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="description" content="{{ subtitle }}">
<title>{{ title }}</title>
<link rel="alternate" type="application/rss+xml" title="{{ title }}" href="feed.xml">
<style>
  /* Bird & Birdin ilme: petroli #005C82, korostus #FFA169, vaalea mintunvihreä
     #EBF8F6. Otsikot Georgialla, leipäteksti groteskilla. Georgia on valmiina
     joka koneessa, joten ulkoisia fonttilatauksia ei tarvita ja sivu pysyy
     yhtenä tiedostona. Se pitää myös kävijän IP-osoitteen poissa Googlen
     palvelimilta, mikä on tietosuojasivulla oma pointtinsa. */
  :root {
    --bg: #f3f8f9; --card: #ffffff; --ink: #10323f; --muted: #4a626e;
    --line: #dae7eb; --accent: #005C82; --hot: #fff3ea; --hotline: #ffc9a3;
    --ok: #1c6b4d; --fail: #9a3412;
    --serif: Georgia, "Times New Roman", "Iowan Old Style", serif;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0d1f27; --card:#142c36; --ink:#e7f1f3; --muted:#a3bcc6;
            --line:#23414d; --accent:#7ec2df; --hot:#2b2119; --hotline:#7a4e2c;
            --ok:#7fd4ad; --fail:#f2a880; }
  }
  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:16px/1.55 "Open Sans", -apple-system, BlinkMacSystemFont, "Segoe UI",
              system-ui, sans-serif;
         overflow-wrap: break-word; }
  .wrap { max-width: 860px; margin: 0 auto; padding: 28px 20px 80px; }

  /* Näppäimistöfokus pitää näkyä. Kaikki suodattimet ovat nappeja ja niitä
     selataan sarkaimella. */
  a:focus-visible, button:focus-visible, input:focus-visible, summary:focus-visible {
    outline: 3px solid var(--accent); outline-offset: 2px; border-radius: 4px; }

  .skip { position:absolute; left:-9999px; }
  .skip:focus { position:static; display:inline-block; margin-bottom:12px;
    padding:8px 12px; background:var(--accent); color:#fff; border-radius:6px; }

  header h1 { font-family: var(--serif); font-weight: 400; font-size: 1.9rem;
    margin: 0 0 6px; letter-spacing: -0.005em; color: var(--accent); }
  header p.lede { margin: 0 0 10px; color: var(--muted);
    font-family: var(--serif); font-style: italic; font-size: 1.02rem; }
  .intro { margin: 14px 0 0; font-size: 0.93rem; max-width: 62ch; }
  .intro p { margin: 0 0 8px; }
  .meta { margin-top: 14px; color: var(--muted); font-size: 0.83rem; }
  .meta a { color: var(--accent); }
  .meta b { color: var(--ink); font-weight: 700; }

  /* Lähdepaneeli. Suljettuna oletuksena, koska se on taustatietoa. */
  details.sources { margin-top:16px; border:1px solid var(--line);
    border-radius:10px; background:var(--card); }
  details.sources > summary { cursor:pointer; padding:11px 14px;
    font-size:0.86rem; font-weight:600; color:var(--accent); }
  details.sources[open] > summary { border-bottom:1px solid var(--line); }
  .srcbody { padding:12px 14px 14px; }
  .srcbody p { margin:0 0 10px; font-size:0.85rem; color:var(--muted); max-width:62ch; }
  ul.srclist { list-style:none; margin:0; padding:0;
    display:grid; grid-template-columns:repeat(auto-fill, minmax(230px, 1fr)); gap:4px 16px; }
  ul.srclist li { font-size:0.82rem; display:flex; gap:8px; align-items:baseline;
    padding:3px 0; border-bottom:1px dotted var(--line); }
  .dot { flex:0 0 auto; font-weight:700; font-size:0.72rem; letter-spacing:0.03em; }
  .dot.ok { color:var(--ok); }
  .dot.fail { color:var(--fail); }
  .srcname { flex:1 1 auto; }
  .srcnum { flex:0 0 auto; color:var(--muted); font-variant-numeric:tabular-nums; }

  /* min-inline-size on fieldsetissä oletuksena min-content, ei 0 kuten
     muilla lohkoelementeillä. Ilman nollausta nappirivi venyttää koko sivun
     leveämmäksi kuin ruutu ja puhelin zoomaa ulos, jolloin teksti näyttää
     yhdeltä pätkältä. */
  fieldset.controls { border:0; margin:22px 0 0; padding:0;
    min-inline-size:0; max-width:100%; }
  fieldset.controls legend { font-size:0.75rem; text-transform:uppercase;
    letter-spacing:0.08em; color:var(--muted); font-weight:700; padding:0;
    margin-bottom:7px; }
  .searchrow { display:flex; gap:8px; flex-wrap:wrap; align-items:center;
    min-width:0; max-width:100%; }
  input[type=search] { flex:1 1 240px; min-width:0; padding:10px 12px;
    border:1px solid var(--line); border-radius:8px; background:var(--card);
    color:var(--ink); font-size:1rem; font-family:inherit; }
  .chiprow { display:flex; gap:7px; flex-wrap:wrap; margin-top:7px;
    min-width:0; max-width:100%; }
  .chip { padding:7px 12px; border:1px solid var(--line); border-radius:999px;
    background:var(--card); color:var(--muted); font-size:0.82rem; cursor:pointer;
    font-family:inherit; white-space:nowrap; }
  .chip:hover { border-color:var(--accent); color:var(--accent); }
  .chip[aria-pressed=true] { background:var(--accent); color:#ffffff; border-color:var(--accent); }
  .chip.reset { border-style:dashed; }
  .count { margin:14px 0 0; font-size:0.83rem; color:var(--muted); }

  .daygroup { margin-top: 26px; }
  .daygroup > h2 { font-size:0.78rem; text-transform:uppercase; letter-spacing:0.09em;
    color:var(--muted); font-weight:700; margin:0 0 10px;
    padding-bottom:6px; border-bottom:1px solid var(--line); }
  article { background:var(--card); border:1px solid var(--line); border-radius:10px;
    padding:14px 16px; margin-bottom:10px; }
  article.hot { background:var(--hot); border-color:var(--hotline); }
  article a.t { font-family:var(--serif); color:var(--ink); text-decoration:none;
    font-weight:600; font-size:1.06rem; line-height:1.4; overflow-wrap:anywhere; }
  article a.t:hover { color:var(--accent); text-decoration:underline; }
  .court { display:inline-block; font-size:0.72rem; font-weight:700; letter-spacing:0.05em;
    text-transform:uppercase; color:var(--accent); margin-bottom:4px; }
  .kw { margin:6px 0 0; color:var(--muted); font-size:0.87rem; }
  .tags { margin-top:8px; display:flex; gap:6px; flex-wrap:wrap; }
  .tag { font-size:0.7rem; color:var(--muted); border:1px solid var(--line);
    padding:2px 7px; border-radius:999px; }
  .tag.topic { color:var(--accent); border-color:var(--accent); }
  .tag.important { color:var(--fail); border-color:var(--hotline); font-weight:700; }
  /* Korallinen "uusi"-merkki on Bird & Birdin korostusväri. Täytetty pilleri,
     koska #FFA169 tekstinä vaalealla taustalla ei täytä kontrastivaatimusta. */
  .tag.new { background:#FFA169; color:#3a1f0c; border-color:#FFA169; font-weight:700; }
  footer { margin-top:48px; padding-top:18px; border-top:1px solid var(--line);
    color:var(--muted); font-size:0.8rem; }
  footer a { color:var(--accent); }
  footer p { margin:0 0 8px; max-width:62ch; }
  .empty { color:var(--muted); padding:36px 0; }

  /* Kapea ruutu. Puhelimessa sivua katsotaan pystyasennossa noin 360
     pikselin levyisenä, ja siinä leveydessä sarakkeet ja isot marginaalit
     vain vievät tilaa. */
  @media (max-width: 560px) {
    .wrap { padding: 20px 14px 56px; }
    header h1 { font-size: 1.5rem; }
    header p.lede { font-size: 0.95rem; }
    .intro { font-size: 0.9rem; }
    ul.srclist { grid-template-columns: 1fr; }
    article { padding: 12px 13px; }
    article a.t { font-size: 1rem; }
    /* Napit vierivät vaakasuunnassa sen sijaan että ne pakkautuisivat
       moneen riviin ja työntäisivät listan ruudun alareunaan. */
    .chiprow { flex-wrap: nowrap; overflow-x: auto; padding-bottom: 6px;
      scrollbar-width: thin; -webkit-overflow-scrolling: touch; }
    .chip { font-size: 0.8rem; padding: 8px 12px; }
  }
  @media (prefers-reduced-motion: reduce) {
    * { scroll-behavior: auto !important; transition: none !important; }
  }
</style>
</head>
<body>
<div class="wrap">
<a class="skip" href="#list">Siirry ratkaisuihin</a>

<header>
  <h1>{{ title }}</h1>
  <p class="lede">{{ subtitle }}</p>

  <div class="intro">
    <p>Sivu kokoaa yhteen tietosuojaa, teknologiaa ja datasääntelyä koskevat
    ratkaisut, valvontapäätökset ja säädösvalmistelun {{ source_total }} lähteestä.
    Mukaan pääsevät jutut, joiden otsikossa, asiasanoissa tai tiivistelmässä on
    ainakin yksi seurattavista termeistä. Aikaikkuna on {{ window_days }} päivää.</p>
    <p>Haku ajetaan automaattisesti arkiaamuisin. Aineisto on julkista ja tulee
    suoraan kunkin viranomaisen omasta syötteestä. Sivulla ei ole seurantaa,
    evästeitä eikä ulkoisia fonttilatauksia.</p>
  </div>

  <p class="meta">
    Päivitetty <b>{{ generated }}</b> · <b>{{ items|length }}</b> ratkaisua ·
    <b>{{ new_count }}</b> uutta edellisen ajon jälkeen ·
    <a href="feed.xml">RSS</a> · <a href="data.json">JSON</a>
  </p>

  <details class="sources">
    <summary>Lähteiden tila: {{ ok_count }}/{{ source_total }} vastasi{% if fail_count %}, {{ fail_count }} ei vastannut{% endif %}</summary>
    <div class="srcbody">
      <p>Luku kertoo, montako juttua lähteestä saatiin ennen avainsanasuodatusta.
      Nolla tarkoittaa, että lähde vastasi mutta sillä ei ollut mitään aikaikkunan
      sisällä. Punainen merkintä tarkoittaa, että lähdettä ei saatu, jolloin sen
      aineisto puuttuu tältä sivulta.</p>
      <ul class="srclist">
        {% for s in statuses %}
        <li>
          <span class="dot {{ 'ok' if s.ok else 'fail' }}" aria-hidden="true">{{ '●' if s.ok else '▲' }}</span>
          <span class="srcname">{{ s.name }}<span class="skip">{{ ', vastasi' if s.ok else ', ei vastannut' }}</span></span>
          <span class="srcnum">{{ s.items|length if s.ok else 'ei saatu' }}</span>
        </li>
        {% endfor %}
      </ul>
      {% if manual_sources %}
      <p style="margin-top:12px">Käsin tarkistettavat lähteet, joista ei saa
      koneluettavaa aineistoa: {{ manual_sources|join(', ') }}.</p>
      {% endif %}
    </div>
  </details>
</header>

<fieldset class="controls">
  <legend>Rajaa</legend>
  <div class="searchrow">
    <label class="skip" for="q">Hakusana</label>
    <input type="search" id="q" placeholder="Hae otsikoista ja asiasanoista">
    <button type="button" class="chip reset" id="reset">Tyhjennä rajaukset</button>
  </div>
  {% if topics %}
  <div class="chiprow" role="group" aria-label="Rajaa aiheen mukaan">
    {% for t in topics %}<button type="button" class="chip" data-topic="{{ t|lower }}" aria-pressed="false">{{ t }}</button>{% endfor %}
  </div>
  {% endif %}
  <div class="chiprow" role="group" aria-label="Rajaa lähteen mukaan">
    {% for c in courts %}<button type="button" class="chip" data-court="{{ c }}" aria-pressed="false">{{ c }}</button>{% endfor %}
  </div>
</fieldset>

<p class="count" id="count" role="status" aria-live="polite">{{ items|length }} ratkaisua näkyvissä</p>

<main id="list">
{% for day, group in grouped %}
  <section class="daygroup">
    <h2>{{ day }}</h2>
    {% for it in group %}
    <article class="{% if 'tärkeä' in it.tags %}hot{% endif %}"
             data-court="{{ it.court }}"
             data-topics="{{ it.topics|join('|')|lower }}"
             data-text="{{ (it.title ~ ' ' ~ it.keywords ~ ' ' ~ it.summary)|lower|e }}">
      <span class="court">{{ it.court }}</span>
      <div><a class="t" href="{{ it.url }}" target="_blank" rel="noopener">{{ it.title }}</a></div>
      {% if it.keywords %}<p class="kw">{{ it.keywords }}</p>{% endif %}
      {% if it.summary and not it.keywords %}<p class="kw">{{ it.summary }}</p>{% endif %}
      <div class="tags">
        {% if it.is_new %}<span class="tag new">uusi</span>{% endif %}
        {% if 'tärkeä' in it.tags %}<span class="tag important">tärkeä</span>{% endif %}
        {% for t in it.topics %}<span class="tag topic">{{ t }}</span>{% endfor %}
        {% for t in it.display_tags %}<span class="tag">{{ t }}</span>{% endfor %}
      </div>
    </article>
    {% endfor %}
  </section>
{% endfor %}
{% if not items %}<p class="empty">Ei osumia valitulla aikavälillä. Löysää avainsanoja sources.yaml-tiedostossa.</p>{% endif %}
<p class="empty" id="noresults" hidden>Rajaukset eivät jätä yhtään ratkaisua näkyviin.</p>
</main>

<footer>
  <p>Lähteet: {{ source_names|join(', ') }}.</p>
  <p>Seuranta on apuväline, ei oikeudellista neuvontaa. Suodatus perustuu
  avainsanoihin, joten se päästää läpi myös epäolennaista ja voi pudottaa
  olennaista. Tarkista ratkaisu aina alkuperäisestä lähteestä ennen kuin
  nojaat siihen.</p>
</footer>
</div>

<script>
const q = document.getElementById('q');
const chips = [...document.querySelectorAll('.chip[data-court], .chip[data-topic]')];
const cards = [...document.querySelectorAll('article')];
const counter = document.getElementById('count');
const none = document.getElementById('noresults');

function apply() {
  const term = q.value.trim().toLowerCase();
  const on = chips.filter(c => c.getAttribute('aria-pressed') === 'true');
  const courts = on.filter(c => c.dataset.court).map(c => c.dataset.court);
  const topics = on.filter(c => c.dataset.topic).map(c => c.dataset.topic);

  let shown = 0;
  cards.forEach(a => {
    const okCourt = !courts.length || courts.includes(a.dataset.court);
    const cardTopics = (a.dataset.topics || '').split('|').filter(Boolean);
    const okTopic = !topics.length || topics.some(t => cardTopics.includes(t));
    const okTerm = !term || a.dataset.text.includes(term);
    const visible = okCourt && okTopic && okTerm;
    a.hidden = !visible;
    if (visible) shown++;
  });

  document.querySelectorAll('.daygroup').forEach(s => {
    s.hidden = ![...s.querySelectorAll('article')].some(a => !a.hidden);
  });

  counter.textContent = shown + ' ratkaisua näkyvissä';
  none.hidden = shown !== 0;
}

q.addEventListener('input', apply);
chips.forEach(c => c.addEventListener('click', () => {
  c.setAttribute('aria-pressed', c.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
  apply();
}));
document.getElementById('reset').addEventListener('click', () => {
  q.value = '';
  chips.forEach(c => c.setAttribute('aria-pressed', 'false'));
  apply();
  q.focus();
});
</script>
</body>
</html>
""")

FI_MONTHS = ["", "tammikuuta", "helmikuuta", "maaliskuuta", "huhtikuuta",
             "toukokuuta", "kesäkuuta", "heinäkuuta", "elokuuta",
             "syyskuuta", "lokakuuta", "marraskuuta", "joulukuuta"]

# Uutiskirjeen lähteet, joista ei saa koneluettavaa aineistoa. Nämä näkyvät
# lähdepaneelissa, jotta sivu kertoo itse mitä se ei kata.
MANUAL_SOURCES = [
    "EDPS", "Puolan UODO", "eduskunnan VaskiData", "Finlexin säädöskokoelma",
]


def fi_date(d: dt.date) -> str:
    return f"{d.day}. {FI_MONTHS[d.month]} {d.year}"


def write_all(items: list[Item], settings: dict, statuses: list[SourceResult],
              out_dir: Path, new_keys: set[str], base_url: str = "") -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    for it in items:
        it.is_new = it.key in new_keys  # type: ignore[attr-defined]

        # Aiheluokka ja osumasana kertovat usein saman asian, esimerkiksi
        # luokka "Kyberturvallisuus" ja osuma "kyberturvallisuus". Näytetään
        # osumista vain ne, jotka tuovat oikeasti uutta tietoa siitä miksi
        # juttu tuli mukaan, ja niistäkin enintään kaksi.
        topic_words = " ".join(it.topics).lower()
        it.display_tags = [  # type: ignore[attr-defined]
            t for t in it.tags
            if t != "tärkeä" and t.lower() not in topic_words
        ][:2]

    grouped: list[tuple[str, list[Item]]] = []
    for it in items:
        label = fi_date(it.date)
        if grouped and grouped[-1][0] == label:
            grouped[-1][1].append(it)
        else:
            grouped.append((label, [it]))

    courts = sorted({it.court for it in items})

    # Aiheluokat järjestetään yleisyyden mukaan, jotta ensimmäinen nappi on
    # myös se joka tuottaa eniten osumia. Tyhjiä luokkia ei näytetä.
    topic_counts: dict[str, int] = {}
    for it in items:
        for t in it.topics:
            topic_counts[t] = topic_counts.get(t, 0) + 1
    topics = sorted(topic_counts, key=lambda t: (-topic_counts[t], t))

    # Lähdepaneeli: toimivat ensin aakkosissa, sitten epäonnistuneet.
    ordered = sorted(statuses, key=lambda s: (not s.ok, s.name.lower()))
    ok_count = sum(1 for s in statuses if s.ok)

    now = dt.datetime.now()

    (out_dir / "index.html").write_text(
        PAGE.render(
            title=settings.get("site_title", "Oikeustapausseuranta"),
            subtitle=settings.get("site_subtitle", ""),
            generated=now.strftime("%-d.%-m.%Y klo %H:%M"),
            items=items,
            grouped=grouped,
            courts=courts,
            topics=topics,
            statuses=ordered,
            source_names=[s.name for s in statuses],
            source_total=len(statuses),
            ok_count=ok_count,
            fail_count=len(statuses) - ok_count,
            manual_sources=MANUAL_SOURCES,
            window_days=settings.get("window_days", 90),
            new_count=len(new_keys),
        ),
        encoding="utf-8",
    )

    _write_rss(items, settings, out_dir, base_url)

    (out_dir / "data.json").write_text(
        json.dumps(
            {
                "generated": now.isoformat(timespec="seconds"),
                "window_days": settings.get("window_days", 90),
                "sources": [
                    {"id": s.source_id, "name": s.name, "court": s.court,
                     "ok": s.ok, "fetched": len(s.items), "error": s.error}
                    for s in statuses
                ],
                "items": [
                    {
                        "court": it.court,
                        "source": it.source_name,
                        "title": it.title,
                        "url": it.url,
                        "date": it.date.isoformat(),
                        "keywords": it.keywords,
                        "summary": it.summary,
                        "score": it.score,
                        "topics": it.topics,
                        "tags": it.tags,
                    }
                    for it in items
                ],
            },
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
        ]
        # Aiheluokat <category>-elementteinä, jotta RSS-lukijassa voi tehdä
        # samat rajaukset kuin sivulla.
        parts += [f"<category>{html.escape(t)}</category>" for t in it.topics]
        parts.append("</item>")
    parts.append("</channel></rss>")
    (out_dir / "feed.xml").write_text("\n".join(parts), encoding="utf-8")
