# Oikeustapausseuranta

Henkilökohtainen uutisvirta tietosuojaa, teknologiaa ja datasääntelyä koskevista
ratkaisuista. Python-skripti hakee ratkaisut tuomioistuinten ja viranomaisten
syötteistä, suodattaa ne avainsanoilla ja kirjoittaa staattisen verkkosivun.
GitHub Actions ajaa haun arkisin aamulla ja GitHub Pages julkaisee sivun.

Ei palvelinta, ei tietokantaa, ei kuukausimaksua.

## Mitä missä tiedostossa on

| Tiedosto | Tehtävä |
|---|---|
| `sources.yaml` | Lähteet ja avainsanat. Tätä muokkaat normaalisti. |
| `fetchers.py` | Lähdekohtaiset hakijat: RSS, SPARQL, HTML-listaus. |
| `filtering.py` | Avainsanasuodatus ja järjestys. |
| `render.py` | HTML-sivu, RSS-syöte ja JSON. |
| `main.py` | Käynnistys ja komentoriviargumentit. |
| `docs/` | Valmis sivu. GitHub Pages näyttää tämän kansion. |
| `state.json` | Muistaa nähdyt ratkaisut, jotta uudet saavat "uusi"-merkin. |

## Käyttöönotto

1. Luo GitHubiin uusi repo, esimerkiksi `oikeusfeed`, ja työnnä nämä tiedostot sinne.
2. Tarkista `.github/workflows/update.yml`. Rivin `--base-url` osoite pitää olla
   `https://KAYTTAJATUNNUS.github.io/REPON-NIMI/`.
3. Mene repon **Settings → Pages**. Valitse Source: *Deploy from a branch*,
   Branch: `main` ja kansio `/docs`. Tallenna.
   Pages toimii ilmaistilillä vain julkisessa repossa.
4. Mene **Actions**-välilehdelle, valitse työnkulku ja paina *Run workflow*.
   Ensimmäinen ajo kestää noin 2 minuuttia, koska EU-kysely on hidas.
5. Sivu löytyy osoitteesta `https://4milan423-del.github.io/newsfeed-test/`.

Lisää osoite puhelimen aloitusnäytölle tai tilaa `feed.xml` RSS-lukijaan.

## Paikallinen ajo

```bash
pip install -r requirements.txt

python main.py --dry-run          # näyttää osumat, ei kirjoita tiedostoja
python main.py                    # kirjoittaa docs-kansion
python main.py --only kko,kho     # vain valitut lähteet
python main.py -v                 # enemmän lokia
```

`--dry-run` on nopein tapa säätää avainsanoja. Muuta `sources.yaml`, aja
uudelleen ja katso mitä tulee läpi.

## Suodatuksen säätäminen

`sources.yaml` sisältää kolme avainsanalistaa:

- `must_any` on portti. Vähintään yhden termin pitää osua otsikkoon,
  asiasanoihin tai tiivistelmään. Jos lista on tyhjä, kaikki pääsee läpi.
- `boost` nostaa jutun tärkeäksi. Nämä näkyvät sivulla korostettuna.
- `never` pudottaa jutun pois, vaikka `must_any` osuisi. Tähän kuuluvat
  esimerkiksi webinaarikutsut ja vuosikertomukset.

Vertailu on yksinkertainen osajonohaku pienillä kirjaimilla. Siksi listassa
on katkaistuja sanoja kuten `henkilötiet`, joka osuu muotoihin
"henkilötieto", "henkilötietojen" ja "henkilötietoja". Suomen taivutus
hoituu tällä ilman regexiä.

Jos osumia tulee liian vähän, kasvata `window_days`-arvoa tai lisää termejä.
Jos roskaa tulee liikaa, siirrä termi `must_any`-listasta pois tai lisää
tarkempi ilmaus `never`-listaan.

## Lähteiden lisääminen

Lähde on yksi merkintä `sources.yaml`-tiedostossa. Koodia ei tarvitse muuttaa,
jos lähdetyyppi on jo olemassa:

```yaml
- id: oma-lahde
  name: "Lähteen nimi sivun alaviitteeseen"
  type: plain_rss          # wp_rss, plain_rss, eu_sparql tai html_list
  court: "TUNNUS"          # lyhenne suodatusnappiin
  weight: 2                # 1-3, vaikuttaa järjestykseen
  optional: true           # virhe ei kaada ajoa
  url: "https://..."
```

Tyypit:

- `wp_rss` on tuomioistuinlaitoksen WordPress-syöte. Nämä antavat asiasanat
  `<category>`-elementteinä, mikä on suodatuksen kannalta tärkein tieto,
  koska otsikko on pelkkä tunnus kuten "KKO:2026:62".
- `plain_rss` on mikä tahansa tavallinen RSS tai Atom.
- `eu_sparql` kysyy unionin tuomioistuimen ratkaisut EU:n Cellar-tietokannasta.
- `html_list` raapii linkit HTML-sivulta. `link_pattern` rajaa mitkä linkit
  kelpaavat.

Uusi lähdetyyppi vaatii funktion `fetchers.py`-tiedostoon ja merkinnän
`FETCHERS`-sanakirjaan.

## Miksi Finlexiä ei käytetä

Finlexillä ei ole avointa oikeuskäytännön rajapintaa. `api.finlex.fi` vastaa
401, `opendata.finlex.fi` vaatii tunnisteen ja Akoma Ntoso -polut
oikeustapauksiin palauttavat 404. Siksi ratkaisut haetaan tuomioistuinten
omilta sivuilta, joilla WordPress tarjoaa syötteen ilman avainta.

Tietosuojavaltuutetun ratkaisut julkaistaan Finlexissä, joten niitä seurataan
toimiston ajankohtaissivulta. Sieltä löytyvät seuraamusmaksut ja
merkittävimmät ratkaisut uutisina.

## Tunnetut rajoitukset

- Hovioikeuksien syötteet palauttavat tällä hetkellä nolla juttua.
  Ne on jätetty `optional: true` -merkinnällä paikalleen, koska osoitteet
  voivat alkaa toimia.
- Unionin tuomioistuimen suomenkielinen toisinto ilmestyy viiveellä.
  Skripti ottaa englanninkielisen asiasanoituksen varalle ja korvaa sen
  suomenkielisellä, kun se on saatavilla.
- HTML-listauksesta päivämäärä ei aina löydy. Silloin juttu saa merkinnän
  "pvm arvioitu" ja päiväksi tulee ajopäivä.
- Seuranta on apuväline. Tarkista ratkaisu aina alkuperäisestä lähteestä
  ennen kuin nojaat siihen.
