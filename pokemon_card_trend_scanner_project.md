# Pokémon Card Trend Scanner – projektisuunnitelma

## 1. Projektin tavoite

Rakennetaan selainpohjainen työkalu, joka etsii Pokémon-korteista kiinnostavia ostokohteita markkinadatan perusteella.

Pääpaino on **raakakorteissa (raw / ungraded)**, ei greidatuissa korteissa.

Ensisijainen käyttötapaus:

- löytää kortteja, joiden **myyntimäärä kasvaa**
- löytää kortteja, jotka ovat **trendaavia USA:ssa**
- verrata USA:n ja EU:n hintoja
- tunnistaa tilanteita, joissa USA:n kysyntä ja hinta ovat jo nousussa mutta EU/Cardmarket ei ole vielä seurannut mukana
- löytää suuria **EU vs USA -hintaeroja**
- rajata haku käyttäjän valitsemaan hintahaarukkaan
- näyttää esimerkiksi **Top 20 / Top 50 / Top 100** kiinnostavinta korttia

Työkalua käytetään ensisijaisesti selaimella, myös puhelimella.

---

# 2. Perusidea

Markkinahypoteesi:

> USA:n Pokémon-korttimarkkina liikkuu usein ennen Eurooppaa.  
> Jos USA:ssa myyntimäärä ja hinta alkavat nousta ennen Cardmarketia, tästä voi syntyä informaatioetu.

Tämän vuoksi ohjelma ei etsi vain halpoja kortteja vaan pyrkii tunnistamaan:

1. kysynnän kasvun
2. myyntimäärän kasvun
3. hinnan nousun
4. tarjonnan vähenemisen
5. USA:n ja EU:n välisen viiveen
6. poikkeuksellisen suuren markkinahinnan eron

---

# 3. Rajaukset

## Korttityyppi

Ensimmäinen varsinainen versio:

- raw / ungraded only
- Pokémon cards
- pääosin English
- Japanese voidaan myöhemmin ottaa erillisenä optiona
- Japanese- ja English-dataa ei koskaan yhdistetä samaan hintasarjaan

## Kunto

Ensisijainen standardi:

- Near Mint
- Mint, jos lähde tarjoaa sen luotettavasti erikseen

Hylätään:

- Excellent
- Good
- Light Played
- Played
- Poor
- Damaged
- Moderately Played jne.

Käytännössä lähtökohtainen benchmark on:

> **English + Near Mint + Raw**

## Hintaluokka

Käyttäjä saa itse määrittää hintahaarukan.

Esimerkkejä:

- €1–10
- €5–20
- €10–30
- €20–50
- €50–100
- €100–500

Alkuperäinen yleinen käyttöalue:

> noin €1–500

---

# 4. Käyttöliittymä

Selainpohjainen sovellus.

Tekniikka ensimmäiseen versioon:

- Python
- Streamlit
- myöhemmin mahdollisesti FastAPI + React/Next.js, jos tarvitaan enemmän suorituskykyä tai parempi mobiilikäyttöliittymä

## Päänäkymän suodattimet

Käyttäjä valitsee:

- Min price
- Max price
- Aikajakso:
  - 7 päivää
  - 14 päivää
  - 30 päivää
- Top:
  - 20
  - 50
  - 100
- Market:
  - USA
  - EU
  - USA + EU comparison
- Language:
  - English
  - Japanese optional
- Condition:
  - Near Mint
  - Mint optional

## Esimerkkitulokset

| Rank | Card | Set | US sold 14d | US price | EU price | Sales growth | Price growth | EU lag |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1 | Card A | Set X | 184 | $18.20 | €11.40 | +82% | +21% | +37% |
| 2 | Card B | Set Y | 151 | $13.80 | €9.10 | +61% | +17% | +29% |

---

# 5. Ensimmäinen skanneri: Trending Raw Cards

## Tavoite

Etsi käyttäjän hintahaarukasta eniten myydyt ja nopeimmin kasvavat raakakortit.

Esimerkiksi:

- hinta $5–20
- viimeiset 14 päivää
- Top 50
- raw
- English
- Near Mint

## Tärkeimmät mittarit

- sold_7d
- sold_14d
- sold_30d
- sold_previous_7d
- sold_previous_14d
- sales_growth_pct
- current_price
- price_7d_ago
- price_30d_ago
- price_change_7d
- price_change_30d
- supply_current
- supply_change_7d

## Esimerkki

```text
Card A

Current price        $14.20
Sold last 7d         34
Sold previous 7d     18
Sales growth         +88.9%

Price 7d ago         $12.60
Price now            $14.20
Price growth         +12.7%
```

Tämä on kiinnostavampi kuin kortti, jonka hinta on noussut mutta myyntimäärä ei ole.

---

# 6. Early Trend -signaali

Tavoite:

> löytää kortti ennen kuin hinnannousu on täysin tapahtunut.

Esimerkkitilanne:

```text
Sales velocity       +95%
Sales volume         +70%
Supply               -20%
Price                +4%
```

Tämä voi olla vahvempi varhainen signaali kuin:

```text
Sales velocity       +5%
Price                +45%
```

Ensimmäisessä kysyntä kiihtyy mutta hinta ei ole vielä täysin reagoinut.

---

# 7. USA → EU Lag Scanner

## Tavoite

Etsi kortteja, joissa USA on jo liikkeessä mutta Eurooppa ei vielä.

Esimerkki:

```text
USA
Current              $42
7d ago               $33
30d ago              $28
Sold 7d              44
Sales growth         +78%

EU / Cardmarket
Current              €27
7d ago               €26
30d ago              €25
```

Signaali:

```text
US price growth      +27%
EU price growth       +4%
US sales growth      +78%
Current EU discount  significant
```

Tämä olisi yksi ohjelman tärkeimmistä ominaisuuksista.

---

# 8. Biggest Price Gaps

Erillinen näkymä:

> USA:n ja EU:n suurimmat hintaerot.

Esimerkki:

```text
US NM raw        $85
EU EN/NM         €52

Difference       ~€27
Gap              ~34%
```

Pelkkä hintaero ei kuitenkaan riitä.

Tarvitaan vähimmäislikviditeetti:

- riittävästi toteutuneita myyntejä
- ei vain yhtä yksittäistä outlier-myyntiä
- ei korttia, jota kukaan ei käytännössä osta

Mahdollinen filtteri:

```text
gap_pct >= 15%
absolute_gap >= €5
sold_30d >= threshold
```

Likviditeettiraja voi riippua kortin hinnasta.

Esimerkiksi:

- €5 kortilta vaaditaan paljon myyntejä
- €300 kortilta jo muutama toteutunut kauppa voi olla riittävä

---

# 9. Grading Scanner – erillinen myöhempi moduuli

Tämä EI kuulu päätrendiskanneriin.

Pääohjelma etsii raw-kortteja.

Myöhemmin voidaan tehdä erillinen näkymä:

> halvat raakakortit, joiden PSA 10 toteutuneet myynnit ovat poikkeuksellisen korkeita.

Esimerkki:

```text
Raw EN/NM          €12
PSA 10 sold median €180
Multiple           15x
```

Tässä PSA 8/9 ei ole tärkeä.

Käyttäjän näkemyksen mukaan:

- PSA 8 ja alle ≈ raw
- PSA 9 usein lähellä raw-hintaa erityisesti moderneissa
- kiinnostava upside tulee PSA 10:stä

PSA 10 -hinnan pitää perustua:

> **viimeisiin toteutuneisiin myynteihin, ei aktiivisiin listauksiin**

Mahdolliset mittarit:

- last PSA10 sold
- median last 5 PSA10 sales
- median last 10 PSA10 sales
- PSA10 sales last 30d
- PSA10 sales last 90d
- days since last sale
- PSA10/raw multiple

Tämä moduuli rakennetaan vasta myöhemmin.

---

# 10. Datalähteet

## TCGplayer

Mahdolliset käyttötavat:

- USA raw market
- toteutuneet myynnit
- current market price
- listing data
- volume / sales count, jos saatavilla

Nykyinen v0.1 käyttää:

> TCGplayerin kuukausittaista Top Selling Pokémon Cards -CSV-dataa.

Hyöty:

- toteutuneet myynnit
- helppo ensimmäinen prototyyppi

Rajoitus:

- kuukausiraportti
- ei vielä 7/14/30 päivän liukuvaa dataa
- ei välttämättä condition-tasoista dataa
- eri printit/kunnon voivat yhdistyä

---

## Cardmarket

EU:n tärkein markkinapaikka.

Haluttu data:

- English
- Near Mint
- raw
- current price
- cheapest listings
- supply
- trend / average
- history

Cardmarket on projektin vaikein integraatio.

Virallinen API ei ole helposti saatavilla uusille käyttäjille.

Siksi Cardmarketia ei kannata käyttää koko korttiuniversumin ensimmäiseen skannaukseen.

Parempi rakenne:

```text
ALL CARDS
↓
USA FILTER
↓
50–200 candidates
↓
CARDMARKET LOOKUP
↓
5–30 strongest signals
```

---

## RareBit

RareBit on kiinnostava erityisesti Cardmarket-datan vuoksi.

API:n kautta näyttää olevan saatavissa ainakin:

- source
- language
- condition
- printing
- price variant
- history
- stats
- supply joissain sarjoissa

Cardmarketille kiinnostava sarja:

```text
source = CARDMARKET
variant = LOWEST_NEAR_MINT
language = en
condition = NEAR_MINT
```

Tärkeä huomio:

RareBitin käyttöliittymän yleinen `Current value` ei ole riittävä tieto.

Esimerkiksi LP-estimaatti voi olla eri asia kuin EN/NM floor.

Ohjelmassa käytetään vain eksplisiittisiä sarjoja:

```text
English
Near Mint
Raw
Correct printing
```

### RareBit API trial

Tämänhetkisen selvityksen mukaan:

- RareBitin varsinainen API ei näyttänyt tarjoavan ilmaista muutaman päivän trialia
- API alkaa maksullisesta Developer-tasosta
- aiemmin keskusteltu 3 päivän API-trial liittyi CardmarketAPI.com-palveluun, ei RareBitiin
- RareBitin normaali sovellus voi tarjota oman free/trial-version, mutta se ei ole sama kuin API

Ennen maksullisen API:n ottamista kannattaa tehdä pieni manuaalinen validointi.

---

## CardmarketAPI.com

Kolmannen osapuolen palvelu.

Mahdollinen käyttötarkoitus:

- live Cardmarket listing -data
- EN
- NM
- halvimmat listaukset
- validaatio RareBitiä vastaan

Ei rakenneta järjestelmää vielä sen varaan ennen erillistä testausta.

---

## eBay

Mahdollinen käyttötarkoitus:

- toteutuneet raw-korttien myynnit
- PSA 10 sold data myöhempään grading-skanneriin

Ongelma:

> virallinen sold-history API -pääsy on rajoitettu.

Aktiivisia listauksia EI käytetä toteutuneen markkinahinnan korvikkeena.

---

## PriceCharting

Mahdollinen käyttötarkoitus:

- massaseulonta
- hintatasot
- ensimmäinen koko universumin filtteri
- mahdollisesti myyntivolyymi

Tarkistettava myöhemmin:

- mitä myyntimäärädataa saa API:sta
- kuinka ajantasainen se on
- raw vs graded -erottelu
- historiadata

---

# 11. Dataidentiteetti

Yksi projektin kriittisimmistä osista.

Samaa korttia ei saa sekoittaa väärään:

- printtiin
- settiin
- kieleen
- conditioniin
- reverse/holo/non-holo-versioon
- graded/raw-versioon

Jokaiselle kortille oma sisäinen ID.

Esimerkkirakenne:

```text
card_id
name
set_name
set_code
card_number
rarity
release_date
variant
printing
language
tcgplayer_product_id
cardmarket_product_id
pricecharting_id
rarebit_id
ebay_search_key
```

---

# 12. Hintadatan rakenne

Esimerkkitaulu:

```text
price_observations

card_id
source
region
currency
price
shipping
condition
language
printing
variant
price_type
observed_at
```

`price_type` voi olla esimerkiksi:

- market
- listing
- sold
- floor
- average
- median

Näitä ei saa sekoittaa keskenään.

---

# 13. Myyntidatan rakenne

```text
sales_observations

card_id
source
region
condition
language
printing
sale_price
currency
quantity
sold_at
```

Aggregaatit:

```text
sales_7d
sales_14d
sales_30d
sales_previous_7d
sales_previous_14d
sales_growth_7d
sales_growth_14d
```

---

# 14. Supply-data

Jos lähde tarjoaa aktiivisten listausten määrän:

```text
supply_current
supply_7d_ago
supply_change_pct
```

Esimerkki kiinnostavasta signaalista:

```text
sales +60%
price +8%
supply -25%
```

---

# 15. Trend Score

Myöhemmin voidaan laskea yhdistetty pistemäärä.

Esimerkki:

```text
Trend Score =
    sales acceleration
  + sales volume
  + price momentum
  + supply contraction
  + US/EU gap
  + EU lag
  + liquidity
```

Painoja ei tarvitse lyödä lukkoon vielä.

Ensimmäisessä versiossa kannattaa näyttää raakadata suoraan.

---

# 16. Korttien seulontaputki

Tavoite on välttää turhia Cardmarket-hakuja.

```text
All Pokémon cards
        ↓
Price filter
        ↓
Liquidity filter
        ↓
US sales / trend scanner
        ↓
50–200 candidates
        ↓
Cardmarket / RareBit lookup
        ↓
US vs EU comparison
        ↓
5–30 strongest opportunities
```

Tämä rakenne on tärkeä sekä nopeuden että API-kulujen vuoksi.

---

# 17. Nykyinen prototyyppi v0.1

Valmiina on Streamlit-pohjainen selainversio.

Nykyiset ominaisuudet:

- käyttäjän hintahaarukka
- Top 10–100
- TCGplayer Top Selling -CSV
- myyntimäärän mukainen ranking
- CSV-export
- selainkäyttö
- mahdollista julkaista Streamlit Community Cloudiin

Nykyinen puute:

- kuukausidata, ei liukuva 7/14/30 d
- ei RareBit-integraatiota
- ei EU-dataa
- ei EN/NM condition-filteriä lähdedatassa
- ei vielä mobiilioptimoitu

---

# 18. Puhelinkäyttö

Tavoite:

> käyttäjän ei tarvitse ajaa Pythonia puhelimessa.

Paras ratkaisu:

```text
Phone
↓
Safari / Chrome
↓
Streamlit web app
↓
Scanner
```

Deployment:

- GitHub
- Streamlit Community Cloud

API-avaimet tallennetaan palvelimen secrets-asetuksiin.

Niitä ei laiteta näkyviin frontend-koodiin.

---

# 19. Mahdollinen lopullinen navigaatio

## 1. Trending

- price range
- 7 / 14 / 30d
- Top 20 / 50 / 100
- sales
- sales acceleration
- price momentum

## 2. US → EU Lag

- US price
- EU price
- US sales growth
- EU price growth
- gap
- lag score

## 3. Biggest Gaps

- suurimmat raw EN/NM hintaerot
- vain riittävästi likvidit kortit

## 4. Card Detail

Näytä:

- kuva
- nimi
- setti
- numero
- printing
- US chart
- EU chart
- sales history
- supply
- links

## 5. Grading Opportunities

Rakennetaan myöhemmin erillisenä.

- raw €5–30
- PSA10 sold history
- last 5 / 10 sales
- PSA10/raw multiple
- PSA10 liquidity

---

# 20. Ensimmäisen oikean version minimivaatimukset

MVP:n pitäisi tehdä seuraavat asiat:

1. hakea raw Pokémon -kortit
2. käyttäjä asettaa min/max hinnan
3. käyttäjä valitsee aikajakson
4. ohjelma hakee toteutuneet myynnit
5. ohjelma laskee myyntimäärät
6. ohjelma järjestää Top 50
7. näyttää myyntimäärän kasvun
8. näyttää hintamuutoksen
9. toimii selaimella
10. toimii puhelimella

EU/Cardmarket voidaan lisätä heti seuraavassa vaiheessa.

---

# 21. TODO

## PRIORITY 1 – toimiva raw trend scanner

- [x] Tee ensimmäinen Streamlit-runko
- [x] Hintaraja
- [x] Top N
- [x] TCGplayer kuukausittainen sold-data
- [x] CSV export
- [ ] Julkaise verkkoon
- [ ] Optimoi käyttöliittymä puhelimelle
- [ ] Löydä päiväkohtainen / 7–30d raw sold -datalähde
- [ ] Lisää 7d
- [ ] Lisää 14d
- [ ] Lisää 30d
- [ ] Lisää previous period vertailu
- [ ] Laske sales acceleration
- [ ] Laske price momentum
- [ ] Näytä Top 50

## PRIORITY 2 – kortti-identiteetti

- [ ] Luo master card database
- [ ] Pokémon card name
- [ ] set
- [ ] card number
- [ ] printing
- [ ] language
- [ ] internal ID
- [ ] TCGplayer ID
- [ ] RareBit ID
- [ ] Cardmarket ID
- [ ] PriceCharting ID
- [ ] estä varianttien sekoittuminen

## PRIORITY 3 – RareBit testaus

- [ ] Hanki RareBit API key
- [ ] Testaa 20–30 oikeaa korttia
- [ ] Tarkista EN/NM
- [ ] Tarkista printing
- [ ] Tarkista Cardmarket LOWEST_NEAR_MINT
- [ ] Tarkista supply
- [ ] Tarkista history endpoint
- [ ] Tarkista stats endpoint
- [ ] Vertaa manuaalisesti Cardmarketin live-listauksiin
- [ ] Dokumentoi virheet / puuttuvat kortit
- [ ] Päätä käytetäänkö RareBitiä tuotannossa

## PRIORITY 4 – EU / Cardmarket

- [ ] Hae vain USA-seulan läpäisseet 50–200 korttia
- [ ] EN only
- [ ] NM only
- [ ] Raw only
- [ ] nykyinen floor
- [ ] mahdollinen avg5
- [ ] supply
- [ ] EU price history
- [ ] EU price momentum

## PRIORITY 5 – US → EU Lag

- [ ] US sales growth
- [ ] US price growth
- [ ] EU price growth
- [ ] EU/US current gap
- [ ] lag calculation
- [ ] liquidity requirement
- [ ] Top lagging cards

## PRIORITY 6 – UI

- [ ] Mobile-first layout
- [ ] isot filter-painikkeet
- [ ] 7 / 14 / 30 d quick buttons
- [ ] € min/max
- [ ] Top 20 / 50 / 100
- [ ] sortable table
- [ ] card images
- [ ] detail page
- [ ] CSV export
- [ ] favorites/watchlist

## PRIORITY 7 – Grading Scanner myöhemmin

- [ ] löydä luotettava PSA10 SOLD -datalähde
- [ ] käytä vain toteutuneita myyntejä
- [ ] last 5 median
- [ ] last 10 median
- [ ] sales 30d / 90d
- [ ] raw EN/NM €5–30
- [ ] PSA10/raw multiple
- [ ] erillinen näkymä, ei sekoiteta raw trend scanneriin

---

# 22. Tärkeät säännöt

## Älä vertaa eri kuntoluokkia

Väärin:

```text
US MP vs EU NM
```

Oikein:

```text
US NM raw vs EU NM raw
```

## Älä vertaa eri kieliä

Väärin:

```text
Japanese vs English
```

Oikein:

```text
English vs English
```

Japanese omana sarjana.

## Älä vertaa graded vs raw päätrendiskannerissa

Pääskanneri:

```text
raw vs raw
```

Grading scanner myöhemmin:

```text
raw vs PSA10 SOLD
```

## Älä käytä aktiivista listahintaa toteutuneena arvona

Aktiivinen listing:

> seller asking price

Sold:

> oikeasti toteutunut hinta

Trendiskannerissa priorisoidaan sold-dataa.

---

# 23. Tekninen arkkitehtuuri

Ensimmäinen vaihe:

```text
Streamlit UI
    ↓
Python data pipeline
    ↓
TCGplayer / other US sold source
    ↓
Pandas processing
    ↓
Ranking
```

Seuraava vaihe:

```text
Streamlit UI
    ↓
Backend
    ├── US sold data
    ├── RareBit
    ├── Cardmarket data
    └── card master data
    ↓
SQLite / PostgreSQL
    ↓
Trend calculations
```

Myöhemmin:

```text
Frontend
    ↓
API
    ↓
PostgreSQL
    ↓
Scheduled collectors
```

---

# 24. Tietokanta

Aluksi SQLite riittää.

Myöhemmin PostgreSQL.

Mahdolliset taulut:

```text
cards
market_prices
sales
supply
daily_metrics
source_mapping
watchlist
```

---

# 25. Scheduled data collection

Kun API:t ovat käytössä, ohjelma kerää snapshotit automaattisesti.

Esimerkiksi:

```text
00:00 US prices
00:30 EU prices
01:00 sales stats
```

Tai kerran / muutaman kerran päivässä API-rajoista riippuen.

Näin rakennetaan oma historia vaikka lähde ei tarjoaisi kaikkea valmiina.

---

# 26. Mahdolliset laskennat

## Sales growth

```text
sales_growth =
(current_period_sales - previous_period_sales)
/
previous_period_sales
```

## Price growth

```text
price_growth =
(current_price - previous_price)
/
previous_price
```

## Market gap

```text
gap_pct =
(us_price_eur - eu_price)
/
us_price_eur
```

## Sales velocity

Esimerkiksi:

```text
sales_per_day = sold_count / days
```

## Acceleration

```text
current_7d_sales_per_day
vs
previous_7d_sales_per_day
```

---

# 27. Esimerkki lopullisesta signaalista

```text
Umbreon XYZ #123

Raw EN/NM

US
Price               $22.40
Price 7d             $19.10
Price change         +17.3%
Sold 7d              82
Previous 7d          41
Sales acceleration   +100%

EU
Cardmarket           €14.90
Price 7d             €14.20
Price change         +4.9%
Supply               -18%

Signal:
US demand rising fast
EU price still lagging
```

Tämä on juuri se tilanne, jota ohjelman on tarkoitus löytää.

---

# 28. Projektin tärkein prioriteetti

Kaikkein tärkein datakysymys on:

> **Mistä saadaan luotettavasti korttikohtaiset toteutuneet raw-myynnit viimeiseltä 7–30 päivältä?**

Kun tämä on ratkaistu, muu järjestelmä on suhteellisen suoraviivainen.

Korttimapping ja Cardmarket-data ovat toiseksi tärkeimmät.

---

# 29. Seuraava konkreettinen kehitysaskel

Rakennetaan v0.2:

- raw only
- mobiiliystävällinen
- min/max price
- Top 50
- source abstraction
- 7 / 14 / 30 d valmiina UI:ssa
- mahdollisuus kytkeä uusi sold-data API ilman käyttöliittymän uudelleenkirjoitusta
- RareBit-integraatiolle valmis adapteri
- erillinen config API-avaimille

Tavoite:

> kun sopiva sold-data API löytyy, se voidaan kytkeä suoraan olemassa olevaan skanneriin.

---

# 30. Yhteenveto

Projektin ydin ei ole pelkkä hintavertailu.

Se on:

> **sales-driven Pokémon market scanner**

joka pyrkii löytämään:

- mitä ostetaan juuri nyt
- mitä ostetaan kiihtyvällä tahdilla
- mitä hinnoitellaan vielä liian halvaksi toisella markkinalla
- missä USA johtaa ja EU seuraa jäljessä

Ensimmäinen varsinainen tuote:

> **Raw Pokémon Trend Scanner**

Myöhemmin erillinen lisämoduuli:

> **Grading Opportunities – Raw → PSA10 SOLD**

Näitä ei sekoiteta samaan signaaliin.
