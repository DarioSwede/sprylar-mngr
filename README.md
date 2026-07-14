# Sprylar Manager

En försäljningscentral för Tradera: bevakar din Gmail-inkorg, tolkar
sålt/betalt/frakt/meddelande-mejl automatiskt, skrapar din publika
Tradera-profil för aktiva annonser (bud, sluttid, pris), och visar allt
i en snygg webbsida — utan att du behöver ha en dator igång.

Byggd som efterföljare till den lokala macOS-POC:en (`Old/`-mappen), och
körs helt utan egen server, i samma anda som [FortPolio](https://darioswede.github.io/FortPolio/):
statisk sida på GitHub Pages.

**OBS:** Sidan är helt öppen — vem som helst med länken kan se ordrar,
köparnamn, belopp, adresser och spårningsnummer. Se avsnittet
"Säkerhet i korthet" nedan.

## Hur det fungerar

```
Gmail (read-only)              Tradera (publik profilsida)
      │                                │
      │  var 5:e minut                 │  var 5:e minut
      ▼                                ▼
scripts/sync_gmail.py        scripts/scrape_tradera.py
      │  tolkar mejl                   │  läser __NEXT_DATA__-JSON
      └────────────────┬───────────────┘
                        ▼
           data/store.json   (committas till repot av Action:en)
                        │
                        │  GitHub Pages serverar filen statiskt
                        ▼
           index.html + assets/app.js
                        │  hämtas och visas direkt i webbläsaren
                        ▼
           Din försäljningscentral, nåbar från vilken enhet som helst
```

Ingen backend-server, ingen databas, ingen hosting-kostnad. GitHub Actions
sköter synken, GitHub Pages sköter visningen.

## Funktioner

- Kategoriserar mejl: sålt, betalt, inlämningskvitto, meddelande,
  frakthandling, faktura.
- Grupperar mejl per order till en tidslinje (Såld → Betald → Frakthandling
  → Inlämnad), visad som ett kanban-bräde med en kolumn per steg.
- Skrapar din publika Tradera-profil för aktiva annonser (Ej sålda-kolumnen):
  titel, pris, antal bud, sluttid.
- Tolkar köpare, belopp, spårningsnummer, ombud, paketmått och QR-kod ur
  Tradera/PostNord/DHL/Schenker-mejlen.
- Månadsvis och årsvis försäljningsstatistik (netto efter frakt).
- Sök och filtrera på vara, köpare, spårningsnummer eller ombud.

## Struktur

| Fil/mapp | Vad den gör |
|---|---|
| `index.html`, `assets/` | Frontend — dashboard |
| `scripts/sync_gmail.py` | Körs av GitHub Action, hämtar & tolkar Gmail |
| `scripts/scrape_tradera.py` | Körs av GitHub Action, hämtar aktiva Tradera-annonser |
| `scripts/shipping_parser.py` | Regex-tolkning av frakt-/spårningsfält |
| `.github/workflows/sync.yml` | Schemat som kör synken var 5:e minut |
| `data/store.json` | Ögonblicksbild av mejl + annonser (skapas av Action:en) |

Kom igång: se **[SETUP.md](SETUP.md)**.

## Om Tradera-skrapningen

`scripts/scrape_tradera.py` hämtar bara din **publika** profilsida
(`tradera.com/profile/items/...`) — samma sida vem som helst kan besöka.
Ingen inloggning eller Tradera-API-nyckel behövs. Sidan är serverrenderad
och innehåller all data om dina aktiva annonser (pris, bud, sluttid) som
ren JSON i sidans `__NEXT_DATA__`-block, vilket scriptet läser direkt.

Skört mot ändringar: om Tradera bygger om sin sida kan JSON-strukturen
ändras och scriptet sluta fungera. Det påverkar bara "Ej sålda"-kolumnen
— Gmail-synken (sålt/betalt/frakt) är opåverkad.

## Säkerhet i korthet

- Gmail-åtkomsten är read-only (`gmail.readonly`).
- OAuth-uppgifter (`GMAIL_CLIENT_ID/SECRET/REFRESH_TOKEN`) ligger som
  GitHub Actions-secrets — aldrig i kod eller i det publika repot.
- `data/store.json` committas i klartext. Eftersom repot och GitHub Pages
  är publika kan **vem som helst med länken** läsa ordrar, köparnamn,
  belopp, adresser och spårningsnummer. Vill du skydda datan igen: lägg
  tillbaka ett lösenord/kryptering, eller gör repot privat (kräver
  GitHub Pro för Pages på privata repon).
- `credentials.json` och `token.json` från den gamla lokala POC:en ska
  **aldrig** committas — de ligger i `.gitignore`.
