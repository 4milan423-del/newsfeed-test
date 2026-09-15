# Oikeustapausseuranta

Henkilökohtainen uutisvirta tietosuojaa, teknologiaa ja datasääntelyä koskevista
ratkaisuista. Python-skripti hakee aineiston 26 lähteestä, suodattaa sen
avainsanoilla ja kirjoittaa staattisen verkkosivun. GitHub Actions ajaa haun
arkisin aamulla ja GitHub Pages julkaisee sivun.

Ei palvelinta, ei tietokantaa, ei kuukausimaksua.

## Mitä missä tiedostossa on

| Tiedosto | Tehtävä |
|---|---|
| `sources.yaml` | Lähteet ja avainsanat. Tätä muokkaat normaalisti. |
| `fetchers.py` | Lähdekohtaiset hakijat: RSS, SPARQL, HTML-listaus, OAI-PMH. |
| `filtering.py` | Avainsanasuodatus ja järjestys. |
| `render.py` | HTML-sivu, RSS-syöte ja JSON. |
| `main.py` | Käynnistys ja komentoriviargumentit. |
| `docs/` | Valmis sivu. GitHub Pages näyttää tämän kansion. |
| `state.json` | Muistaa nähdyt ratkaisut, jotta uudet saavat "uusi"-merkin. |

## Lähteet

Lähteet on ryhmitelty `sources.yaml`-tiedostossa samalla logiikalla kuin
Bird & Birdin kuukausittainen tietosuojauutiskirje, jotta sama aineisto tulee
katetuksi automaattisesti:

| Aihe | Lähteet |
|---|---|
| Kansallinen oikeuskäytäntö | KKO, KHO, markkinaoikeus, vakuutusoikeus, työtuomioistuin, Helsingin ja Turun hovioikeus |
| EU | unionin tuomioistuin (SPARQL), curia-tiedotteet, komission digitaalinen strategia |
| Säädösvalmistelu | valtioneuvosto, oikeusministeriö, LVM, TEM |
| Valvontaviranomaiset | tietosuojavaltuutettu, Traficom, EDPB |
| Oikeudelliset julkaisut | Helda, Lauda, UTUPub, UEF eRepo, JYX, Doria |
| Kyberturvallisuus | Kyberturvallisuuskeskus, ENISA (uutiset ja julkaisut) |

Osa uutiskirjeen lähteistä jää käsityöksi, koska niistä ei saa koneluettavaa
aineistoa. EDPS vastaa jokaiseen pyyntöön HTTP 202 ja tyhjällä rungolla,
Puolan UODO ei tarjoa syötettä lainkaan, eduskunnan VaskiData palauttaa
`XmlData`-möykkyjä ilman käyttökelpoista päivämääräsaraketta ja Finlexin
säädöskokoelma rakennetaan selaimessa. Näitä kannattaa vilkaista käsin, jos
uutiskirjeen taso on tavoite.

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

Näiden lisäksi on kaksi lähdekohtaista asetusta, jotka toimivat eri tasolla:

- `always_include: true` päästää lähteen jutut läpi ilman `must_any`-osumaa.
  Tämä on tietosuojavaltuutetulla ja EDPB:llä, koska ne käsittelevät jo
  valmiiksi vain tietosuojaa. `never`-lista pätee silti.
- `require_any` on lähteen oma lisäportti, joka ajetaan ennen globaalia
  suodatusta. Julkaisuarkistoissa se vaatii oikeustieteellisen termin.
  Ilman sitä feediin päätyi konenäköä käsitteleviä diplomitöitä, koska termi
  "tekoäly" osui `must_any`-listaan.

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
  type: plain_rss          # wp_rss, plain_rss, eu_sparql, html_list, oai_pmh
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
- `oai_pmh` hakee yliopistojen julkaisuarkistot. Asetukset ovat
  `lookback_days` (kuinka kaukaa taaksepäin haetaan), `max_pages` (yksi sivu
  on 100 tietuetta) ja `type_contains` (millaiset julkaisutyypit kelpaavat).

Valtioneuvoston hallinnonalan sivut pyörivät Liferaylla, joka tarjoaa RSS:n
osoitteessa `/<sivu>/-/asset_publisher/<TUNNUS>/rss`. Tunnusta ei näy
käyttöliittymässä, joten se pitää kaivaa sivun HTML-lähteestä. Tietosuoja.fi
ja tem.fi toimivat näin. Valtioneuvosto.fi ja lvm.fi eivät tarjoa syötettä
lainkaan, joten ne raavitaan `html_list`-tyypillä.

DSpace-arkistoissa on yksi ansa. Versio 7 siirsi OAI-rajapinnan polkuun
`/server/oai/request`, kun vanhemmat asennukset käyttävät polkua
`/oai/request`. Helda, UTUPub ja UEF ovat uudella polulla, Lauda ja Doria
vanhalla. Väärä polku palauttaa 404 tai nolla tietuetta ilman virheilmoitusta.

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
- Julkaisuarkistot ovat hitaita ja epätasaisia. Yhdestä yliopistosta voi tulla
  kymmeniä osumia ja toisesta yksi, koska tietueiden asiasanoitus vaihtelee.
  Tampereen Trepo jätettiin pois, koska yhteys aikakatkeaa toistuvasti.
- `oai_pmh` tarvitsee `lxml`-kirjaston, koska BeautifulSoupin XML-jäsennin ei
  toimi ilman sitä. Se on `requirements.txt`-tiedostossa.
- Seuranta on apuväline. Tarkista ratkaisu aina alkuperäisestä lähteestä
  ennen kuin nojaat siihen.
