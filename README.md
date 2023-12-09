GPP
----

En kommandolinjeklient for OpenAIs GPT modeller.

## Installasjon

En forutsetning er at Python 3  og [Poetry](https://python-poetry.org) er installert.

Installer ved å kjøre `poetry install`. Deretter kan det være praktisk å kjøre
`poetry shell` for å gjøre korrekt versjon av Python og skript tilgjengelig. Alternativ
kan være å installere en lenke til skriptet:

```sh
ln -s $(poetry run type --path gpp) ~/bin/gpp
```

Skaff deg en [OpenAI API-token](https://platform.openai.com/account/api-keys) og gjør den tilgjengelig fra miljøvariabelen `OPENAI_API_KEY`, alternativt
lagre den i filen `~/.gpp/openai-key.txt`.

## Bruk

Normalt vil du kjøre `gpp` med spørsmålet ditt som argument. Eksempel:

```sh
$ gpp Hvilke uglearter er observert i Norge\?
```

Her er backslash `\` før `?` nødvendig for å unngå at shellet prøver å ekspandere
filnavn som starter med "Norge".  Alternativ er å sette hele spørsmålet i mellom
apostrofer eller å kjøre `gpp` uten argument slik at den leser spørsmålet fra `stdin`.
Hvis du ikke bruker et Unix shell så vil det være andre regler for hvordan argumenter
evalueres og sendes inn til programmer som `gpp`.

Hvis du vil fortsette på siste samtale istedenfor å starte en ny så gir du opsjonen `--continue` (som kan forkortes til `-c`).
Alternativ er å starte teksten med én eller flere punktumer, som f.eks dette:

```sh
$ gpp ...Kan du sette opp en tabell over artene\? Ta med vingespenn og vekt.
```

Spesielle kommandoer som gjenkjennes er:

* `gpp list [<n> | all | files]`: Denne lister opp de siste samtalene du har hatt. Her er `<n>` antall samtaler som listes opp, hvor `7` er standardverdi.  Tallet som oppgis først på hver linje er det som du kan bruke med `gpp recall` for å se hele samtalen.

* `gpp recall [<n>]`: Denne skriver ut den n'te siste samtalen du har hatt. Standardverdi for `<n>` er 1, som da er siste samtale.

Personligheten til `gpp` kan styres ved å oppgi din egen system prompt with opsjonen `--system`. Her kan du enten oppgi en fullstendig setning, eller bare navnet på en fil som du oppretter under `~/.gpp/system/`-katalogen.  Du kan også redigere
standardoppførselen til gpp ved å redigere direkte i filen `~/.gpp/system/default`.

Systemfilene kan også prefikses med en JSON-objekt som f.eks. kan brukes til å overstyre standardverdiene for parametere
til konversasjonen.  Her kan du f.eks. velge model eller temperatur.  For detaljer om hva som kan styres her se
API-dokumentasjonen lenket til nedenfor.

Kjør `gpp --help` for å lære deg hvilke andre opsjoner du kan bruke sammen med kommandoen.

## Se også

https://platform.openai.com/docs/guides/gpt/chat-completions-api beskriver APIet som brukes.

https://llm.datasette.io et et tilsvarende verktøy skrevet av Simon Willison.