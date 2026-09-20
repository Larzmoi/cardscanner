# Pokémon Card Scanner v0.2

Selainpohjainen raw Pokémon -korttien trendiskanneri.

## Nykyinen käyttötapaus: US → EU -arbitraasin esiseulonta

Sovelluksen tärkein työnkulku on nyt kaksivaiheinen:

1. **Seulonta:** etsi USA:n TCGplayer/Near Mint -markkinasta esimerkiksi
   5–20 dollarin kortit, joilla on likviditeettiä ja hintamomentumia.
2. **Vahvistus:** hae ehdokkaille PokeTrace-historian päiväkohtaiset rivit ja
   laske oikea TCGplayerin toteutunut 30 päivän myyntimäärä.

`TCG sales hist.` on vain kumulatiivinen seulontaproxy. Sitä ei saa tulkita
30 päivän myynneiksi. Oikea 30d-luku näkyy vasta, kun **Vahvista TCGplayer
30d** on ajettu PokeTrace Pro+ -historialla.

EU-arbitraasi edellyttää vielä saman kortin, printin, kielen ja Near Mint
raw -kunnon Cardmarket- tai RareBit-dataa. PriceChartingin `loose-price` ja
`sales-volume` ovat tukevia ristiinvertailuja, eivät EU-hinnan korvikkeita.
Sovellus näyttää tämän puuttuvan validointikerroksen eksplisiittisesti eikä
valmista keinotekoista EU-signaalia.

## v0.2

Uutta:

- TCGplayer Top Selling -näkymä
- hintahaarukka
- Top 10 / 20 / 30 / 50 / 75 / 100
- TCGplayer 30 päivän Near Mint Price Trends -näkymä
- yhdistelmänäkymä: kortit, jotka ovat sekä Top Selling- että 30d-nousijoissa
- PriceCharting API -integraatio:
  - raw / ungraded nykyhinta (`loose-price`)
  - vuosittainen myyntivolyymi (`sales-volume`)
- PriceCharting ei ole pakollinen; muu appi toimii ilman tokenia
- raw only -periaate säilytetty
- RareBit/Cardmarket jätetty seuraavaan vaiheeseen

## TCGplayerin datan rajoitukset

Top Selling -kuukausiraportti:
- toteutunut myyntivolyymi / ranking
- ei erottele conditionia
- ei erottele printing-versioita

Price Trends -raportti:
- Near Mint
- vähintään 10 myyntiä raporttijaksolla
- noin 30 päivän hinnanmuutos
- ei ole jatkuva live-API

## PriceCharting

PriceCharting API on valinnainen ja vaatii oman API-tokenin.

Korttien kannalta:
- `loose-price` = raw / ungraded
- `sales-volume` = yearly units sold

PriceCharting ei anna tässä API:ssa historiallista 7/30 päivän myyntidataa.

### Streamlit Secrets

Pilvessä token kannattaa lisätä:

App → Settings → Secrets

```toml
PRICECHARTING_TOKEN = "OMA_TOKEN"
```

Älä committaa API-tokenia GitHubiin.

## Päivitys GitHubiin

Korvaa vanha `app.py` tällä v0.2-versiolla ja varmista, että
`requirements.txt` on mukana.

Sen jälkeen:

```powershell
git add .
git commit -m "Update scanner to v0.2"
git push
```

Streamlit Community Cloud päivittää sovelluksen GitHubista automaattisesti.
