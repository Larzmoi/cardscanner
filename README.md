# Pokémon Trend Scanner v0.5 RESET

Tämä versio palauttaa alkuperäisen tavoitteen.

- vain English Pokémon singles
- raw / Near Mint
- alle $1 pois
- Energy-kortit pois oletuksena
- historiallista saleCountia ei käytetä trendin päämittarina
- vaaditaan positiivinen 7d vs 30d hintamomentum
- lyhyen aikavälin voimakas pudotus hylätään
- Free PokeTrace käyttää saleCountia vain likviditeetin vahvistuksena
- Pro+ history laskee Myyty 7d / 14d / 30d ja sales accelerationin

## Päivitys

Korvaa `app.py` ja `requirements.txt`, sitten:

```powershell
git add app.py requirements.txt
git commit -m "Reset scanner to growth candidates"
git push
```
