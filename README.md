# Sprylar Manager

En privat försäljningscentral för Tradera: bevakar din Gmail-inkorg, tolkar
sålt/betalt/frakt/meddelande-mejl automatiskt och visar allt i en snygg,
lösenordsskyddad webbsida — utan att du behöver ha en dator igång.

Byggd som efterföljare till den lokala macOS-POC:en (`Old/`-mappen), men
körs nu helt utan egen server, i samma anda som [FortPolio](https://darioswede.github.io/FortPolio/):
statisk sida på GitHub Pages, data krypterad i repot, upplåst med lösenord
i webbläsaren.

## Hur det fungerar

```
Gmail (read-only)
      │
      │  var 5:e minut
      ▼
GitHub Action (scripts/sync_gmail.py)
      │  tolkar mejl, krypterar med ditt lösenord (AES-256-GCM)
      ▼
data/store.enc.json   (committas till repot av Action:en)
      │
      │  GitHub Pages serverar filen statiskt
      ▼
index.html + assets/app.js
      │  du anger lösenord → dekrypteras lokalt i webbläsaren
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
- Lösenordsskärm — data är krypterad i vila, även i det publika repot.

## Struktur

| Fil/mapp | Vad den gör |
|---|---|
| `index.html`, `assets/` | Frontend — lösenordslås + dashboard |
| `scripts/sync_gmail.py` | Körs av GitHub Action, hämtar & tolkar Gmail |
| `scripts/shipping_parser.py` | Regex-tolkning av frakt-/spårningsfält |
| `scripts/crypto_utils.py` | Kryptering (måste matcha `assets/crypto.js`) |
| `.github/workflows/sync.yml` | Schemat som kör synken var 5:e minut |
| `data/store.enc.json` | Krypterad ögonblicksbild (skapas av Action:en) |

Kom igång: se **[SETUP.md](SETUP.md)**.

## Säkerhet i korthet

- Gmail-åtkomsten är read-only (`gmail.readonly`).
- OAuth-uppgifter (`GMAIL_CLIENT_ID/SECRET/REFRESH_TOKEN`) och lösenordet
  (`ENCRYPTION_PASSWORD`) ligger som GitHub Actions-secrets — aldrig i kod
  eller i det publika repot.
- `data/store.enc.json` är krypterat med ditt lösenord innan det committas.
  Repot kan vara publikt utan att sälj-/köpardata läcker.
- `credentials.json` och `token.json` från den gamla lokala POC:en ska
  **aldrig** committas — de ligger i `.gitignore`.
