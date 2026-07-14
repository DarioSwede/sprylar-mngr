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
Lägg till tre secrets. Värdena finns i `SECRETS_TO_COPY.txt` (skapad
lokalt åt dig, committas aldrig — radera filen när du är klar):

| Namn | Värde |
|---|---|
| `GMAIL_CLIENT_ID` | från `SECRETS_TO_COPY.txt` |
| `GMAIL_CLIENT_SECRET` | från `SECRETS_TO_COPY.txt` |
| `GMAIL_REFRESH_TOKEN` | från `SECRETS_TO_COPY.txt` |

## 4. Aktivera GitHub Pages

Repo → **Settings → Pages** → Source: **Deploy from a branch** → Branch:
`main`, mapp `/ (root)` → Save.

## 5. Kör igång synken

Repo → **Actions** → välj workflowet **Synka Gmail** → **Run workflow**
(det annars schemalagda 5-minutersintervallet börjar automatiskt efter
detta). Första körningen gör en full genomgång av inkorgen och kan ta
någon minut.

## 6. Öppna sidan

Din sida ligger på `https://<ditt-användarnamn>.github.io/sprylar-manager/`
och är öppen direkt utan lösenord.

## Efteråt

- Radera `SECRETS_TO_COPY.txt` lokalt när du kopierat in värdena.
- De gamla lokala filerna `credentials.json`, `token.json` och `Old/`-mappen
  behövs inte längre för webbversionen — låt dem ligga kvar lokalt (utanför
  git) om du vill kunna felsöka, men de ska aldrig committas.
