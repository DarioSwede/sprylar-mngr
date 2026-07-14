# Kom igång

## 1. Kontrollera Google Cloud-projektet (viktigt!)

Din nuvarande OAuth-klient (`credentials.json`, projekt `sprylar-manager`)
kan stå i **testläge**, och då slutar refresh-token fungera efter 7 dagar —
synken skulle då sluta fungera tyst i bakgrunden.

1. Gå till [Google Cloud Console](https://console.cloud.google.com/apis/credentials/consent)
   → välj projektet `sprylar-manager`.
2. Under **Publishing status**, om det står "Testing": klicka **Publish app**
   och bekräfta. Du behöver ingen Google-granskning för `gmail.readonly`
   med enbart dig själv som användare — bara publiceringssteget.

## 2. Skapa GitHub-repot

1. Skapa ett nytt **publikt** repo på GitHub, t.ex. `sprylar-manager`.
2. Push:a innehållet i den här mappen (`github_repo/`) till repot:

   ```bash
   cd github_repo
   git init
   git add .
   git commit -m "Sprylar Manager – webbversion"
   git branch -M main
   git remote add origin https://github.com/<ditt-användarnamn>/sprylar-manager.git
   git push -u origin main
   ```

## 3. Lägg till secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**.
Lägg till fyra secrets. Värdena för de tre första finns i
`SECRETS_TO_COPY.txt` (skapad lokalt åt dig, committas aldrig — radera
filen när du är klar):

| Namn | Värde |
|---|---|
| `GMAIL_CLIENT_ID` | från `SECRETS_TO_COPY.txt` |
| `GMAIL_CLIENT_SECRET` | från `SECRETS_TO_COPY.txt` |
| `GMAIL_REFRESH_TOKEN` | från `SECRETS_TO_COPY.txt` |
| `ENCRYPTION_PASSWORD` | **välj ett eget lösenord** — det du senare skriver in på sidan. Finns ingen återställning om du glömmer det; du får då köra en ny full synk med ett nytt lösenord. |

## 4. Aktivera GitHub Pages

Repo → **Settings → Pages** → Source: **Deploy from a branch** → Branch:
`main`, mapp `/ (root)` → Save.

## 5. Kör igång synken

Repo → **Actions** → välj workflowet **Synka Gmail** → **Run workflow**
(det annars schemalagda 5-minutersintervallet börjar automatiskt efter
detta). Första körningen gör en full genomgång av inkorgen och kan ta
någon minut.

## 6. Öppna sidan

Din sida ligger på `https://<ditt-användarnamn>.github.io/sprylar-manager/`.
Ange lösenordet du satte som `ENCRYPTION_PASSWORD` i steg 3.

## Efteråt

- Radera `SECRETS_TO_COPY.txt` lokalt när du kopierat in värdena.
- De gamla lokala filerna `credentials.json`, `token.json` och `Old/`-mappen
  behövs inte längre för webbversionen — låt dem ligga kvar lokalt (utanför
  git) om du vill kunna felsöka, men de ska aldrig committas.
- Vill du byta lösenord senare: uppdatera `ENCRYPTION_PASSWORD`-secreten och
  kör workflowet manuellt en gång — skriptet märker att det inte längre kan
  dekryptera gamla `store.enc.json` och gör automatiskt en ny full synk med
  det nya lösenordet.
