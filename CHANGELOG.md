# Changelog

## v0.5

- Uudistettu käyttöliittymä kahden vaiheen työnkuluksi: seulonta ja 30d-vahvistus.
- Lisätty signal score sekä `Early trend` / `Vahva kysyntä` -luokat.
- TCGplayerin toteutunut 30 päivän myynti nostettu näkyväksi vertailusarjaksi.
- Kumulatiivinen `saleCount` merkitään nyt proxyksi, ei 30d-myynniksi.
- Lisätty selkeä US → EU -validointinäkymä ja datalähteiden tila.
- Historiapyyntöjen virheet näytetään käyttäjälle; tyhjää arvoa ei tulkita nollamyynniksi.

## v0.2

- Lisätty TCGplayer 30d Price Trends / Near Mint -näkymä.
- Lisätty hintasuodatus 30d movers -dataan.
- Lisätty "Myynti + nousu" -ristiintaulukointi.
- Lisätty valinnainen PriceCharting API -haku.
- PriceChartingissa käytetään vain raw / ungraded hintaa ja vuosimyyntiä.
- Graded-hinnat jätetään pääscannerista pois.
- RareBit/Cardmarket jää myöhempään EU-integraatioon.
