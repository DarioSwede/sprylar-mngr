# Sprylar Manager

En försäljningscentral för Tradera: bevakar din Gmail-inkorg, tolkar
sålt/betalt/frakt/meddelande-mejl automatiskt och visar allt i en snygg
webbsida — utan att du behöver ha en dator igång.

Byggd som efterföljare till den lokala macOS-POC:en (`Old/`-mappen), och
körs helt utan egen server, i samma anda som [FortPolio](https://darioswede.github.io/FortPolio/):
statisk sida på GitHub Pages.

**OBS:** Sidan är helt öppen — vem som helst med länken kan se ordrar,
köparnamn, belopp, adresser och spårningsnummer. Se avsnittet
"Säkerhet i korthet" nedan.

## Hur det fungerar

```
Gmail (read-only)
      │
      │  var 5:e minut
      ▼
GitHub Action (scripts/sync_gmail.py)
      │  tolkar mejl
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
  → Inlämnad).
- Tolkar köpare, belopp, spårningsnummer, ombud, paketmått och QR-kod ur
  Tradera/PostNord/DHL/Schenker-mejlen.
- Månadsvis och årsvis försäljningsstatistik (netto efter frakt).
- Sök och filtrera på vara, köpare, spårningsnummer eller ombud.

## Struktur

| Fil/mapp | Vad den gör |
|---|---|
| `index.html`, `assets/` | Frontend — dashboard |
| `scripts/sync_gmail.py` | Körs av GitHub Action, hämtar & tolkar Gmail |
| `scripts/shipping_parser.py` | Regex-tolkning av frakt-/spårningsfält |
| `.github/workflows/sync.yml` | Schemat som kör synken var 5:e minut |
| `data/store.json` | Ögonblicksbild av tolkade mejl (skapas av Action:en) |

Kom igång: se **[SETUP.md](SETUP.md)**.

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
