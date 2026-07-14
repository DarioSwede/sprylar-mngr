#!/usr/bin/env python3
"""Körs av .github/workflows/sync.yml på ett schema (var 5:e minut).

Hämtar nya/nyligen aktiva mejl från Gmail (read-only), kategoriserar
och tolkar dem (order, köpare, belopp, frakt, QR-kod), och sparar en
krypterad ögonblicksbild i data/store.enc.json som frontend läser och
låser upp med lösenord i webbläsaren.

Miljövariabler (sätts som GitHub Actions-secrets, se SETUP.md):
  GMAIL_CLIENT_ID
  GMAIL_CLIENT_SECRET
  GMAIL_REFRESH_TOKEN
  ENCRYPTION_PASSWORD
  RECENT_LIMIT (valfri, default 150)
"""
from __future__ import annotations

import base64
import json
import os
import re
import struct
import sys
import time
from email.utils import parseaddr
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crypto_utils import decrypt_json, encrypt_json  # noqa: E402
from shipping_parser import choose_qr_image, parse_shipping_fields  # noqa: E402

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
BASE = Path(__file__).resolve().parent.parent
STORE = BASE / "data" / "store.enc.json"
RECENT_LIMIT = int(os.environ.get("RECENT_LIMIT", "150"))


def env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"Saknar miljövariabel {name}. Se SETUP.md.")
    return value


def load_credentials() -> Credentials:
    creds = Credentials(
        None,
        refresh_token=env("GMAIL_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=env("GMAIL_CLIENT_ID"),
        client_secret=env("GMAIL_CLIENT_SECRET"),
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def hdr(headers, name):
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def b64(s):
    if not s:
        return b""
    try:
        return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
    except Exception:
        return b""


def clean_html(v):
    v = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", v)
    v = re.sub(r"(?s)<br\s*/?>", "\n", v)
    v = re.sub(r"(?s)</(p|div|tr|li|h\d)>", "\n", v)
    v = re.sub(r"(?s)<[^>]+>", " ", v)
    v = v.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", v)).strip()


def dims(data, mime):
    try:
        if mime == "image/png" and data[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", data[16:24])
        if mime in ("image/jpeg", "image/jpg") and data[:2] == b"\xff\xd8":
            i = 2
            while i < len(data) - 9:
                if data[i] != 255:
                    i += 1
                    continue
                marker = data[i + 1]
                i += 2
                if marker in (216, 217):
                    continue
                ln = int.from_bytes(data[i:i + 2], "big")
                if marker in range(192, 196):
                    h = int.from_bytes(data[i + 3:i + 5], "big")
                    w = int.from_bytes(data[i + 5:i + 7], "big")
                    return w, h
                i += ln
    except Exception:
        pass
    return 0, 0


def parts(service, mid, payload):
    plain, html, images = [], [], []

    def walk(p):
        mime = p.get("mimeType", "")
        body = p.get("body", {}) or {}
        raw = b64(body.get("data", ""))
        if not raw and body.get("attachmentId"):
            try:
                raw = b64(service.users().messages().attachments().get(
                    userId="me", messageId=mid, id=body["attachmentId"]).execute().get("data", ""))
            except Exception:
                raw = b""
        if mime == "text/plain" and raw:
            plain.append(raw.decode("utf-8", errors="replace"))
        elif mime == "text/html" and raw:
            html.append(raw.decode("utf-8", errors="replace"))
        elif mime in ("image/png", "image/jpeg", "image/jpg") and raw and len(raw) <= 700000:
            w, h = dims(raw, mime)
            images.append({
                "filename": p.get("filename", ""),
                "content_id": hdr(p.get("headers", []), "Content-ID"),
                "width": w, "height": h, "size": len(raw),
                "data_url": f"data:{mime};base64," + base64.b64encode(raw).decode("ascii"),
            })
        for c in p.get("parts", []) or []:
            walk(c)

    walk(payload)
    return "\n".join(plain), "\n".join(html), images


def first(patterns, text):
    for p in patterns:
        m = re.search(p, text, re.I | re.M | re.S)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    return ""


def parse_money(patterns, text):
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            raw = m.group(1).replace("\xa0", "").replace(" ", "").replace(".", "").replace(",", ".")
            try:
                return float(raw)
            except Exception:
                pass
    return None


def thread_status(service, tid, account):
    try:
        th = service.users().threads().get(
            userId="me", id=tid, format="metadata", metadataHeaders=["From"]).execute()
        rows = []
        for m in th.get("messages", []):
            addr = parseaddr(hdr(m.get("payload", {}).get("headers", []), "From"))[1].lower()
            rows.append((int(m.get("internalDate", "0")), addr))
        rows.sort()
        if not rows:
            return False, False
        return any(x == account.lower() for _, x in rows), rows[-1][1] == account.lower()
    except Exception:
        return False, False


def compact_tracking(v):
    return re.sub(r"[^A-Z0-9]", "", (v or "").upper())


def fetch_message(service, mid, account):
    m = service.users().messages().get(userId="me", id=mid, format="full").execute()
    payload = m.get("payload", {})
    headers = payload.get("headers", [])
    plain, html, images = parts(service, mid, payload)
    body = plain.strip() or clean_html(html)
    subject = hdr(headers, "Subject") or "(utan ämne)"
    combined = f"{subject}\n{body}\n{m.get('snippet', '')}"

    sale = parse_money([r"(?:Varupris|Pris|Belopp|Såld för|Försäljningspris)\s*:?\s*([\d .]+(?:,\d{1,2})?)\s*kr"], combined)
    ship = parse_money([r"(?:Frakt|Fraktkostnad|Fraktpris)\s*:?\s*([\d .]+(?:,\d{1,2})?)\s*kr"], combined)
    total = parse_money([r"(?:Totalt|Totalpris|Att betala)\s*:?\s*([\d .]+(?:,\d{1,2})?)\s*kr"], combined)

    objm = re.findall(r"\((\d{8,10})\)", subject)
    obj = objm[-1] if objm else first(
        [r"\bObjektnr\.?\s*:?\s*(\d{8,10})\b", r"\bObjektnummer\s*:?\s*(\d{8,10})\b", r"\bObjekt\s*:?\s*(\d{8,10})\b"],
        body,
    )

    bm = re.search(r"\bKöpare:\s*(.+?)\s*$", subject, re.I)
    buyer = bm.group(1).strip() if bm else first([r"\bKöpare\s*:?\s*([^\n,.;]{2,80})"], body)

    has_reply, latest_is_mine = thread_status(service, m.get("threadId", ""), account)

    tracking = compact_tracking(first([
        r"Spårningsnr\.?\s*:?\s*([A-Z0-9][A-Z0-9\s\-]{8,60})",
        r"Sändningsnummer\s*:?\s*([A-Z0-9][A-Z0-9\s\-]{8,60})",
        r"Kollinummer\s*:?\s*([A-Z0-9][A-Z0-9\s\-]{8,60})",
    ], combined))
    shipment = compact_tracking(first([
        r"Sändningsnr\.?\s*:?\s*([A-Z0-9][A-Z0-9\s\-]{8,60})",
        r"Sändningsnummer\s*:?\s*([A-Z0-9][A-Z0-9\s\-]{8,60})",
    ], combined))

    out = {
        "id": m.get("id", ""),
        "thread_id": m.get("threadId", ""),
        "from": hdr(headers, "From"),
        "to": hdr(headers, "To"),
        "subject": subject,
        "date": hdr(headers, "Date"),
        "internal_date": int(m.get("internalDate", "0")),
        "snippet": m.get("snippet", ""),
        "body": body,
        "unread": "UNREAD" in m.get("labelIds", []),
        "labels": m.get("labelIds", []),
        "url": f"https://mail.google.com/mail/#all/{mid}",
        "order": first([r"\bOrdernummer\s*:?\s*(\d{7,12})\b"], combined),
        "object_id": obj,
        "buyer": buyer,
        "sale_amount": sale,
        "shipping_cost": ship,
        "total_amount": total,
        "thread_has_reply": has_reply,
        "latest_message_is_mine": latest_is_mine,
        "shipment_number": shipment,
        "qr_code_data_url": choose_qr_image(images, html),
    }
    out.update(parse_shipping_fields(subject, body, html))
    return out


def list_message_ids(service, limit):
    """limit=0 -> hämta alla (för första fulla synken)."""
    out, page = [], None
    while True:
        page_size = 500 if not limit else min(500, limit - len(out))
        if page_size <= 0:
            break
        r = service.users().messages().list(
            userId="me", labelIds=["INBOX"], maxResults=page_size, pageToken=page).execute()
        out.extend(x["id"] for x in r.get("messages", []))
        page = r.get("nextPageToken")
        if not page or (limit and len(out) >= limit):
            break
    return out


def main():
    password = env("ENCRYPTION_PASSWORD")
    service = build("gmail", "v1", credentials=load_credentials(), cache_discovery=False)
    account = service.users().getProfile(userId="me").execute().get("emailAddress", "")
    print(f"Ansluten till {account}")

    store = {"emails": [], "last_sync": 0}
    if STORE.exists():
        try:
            store = decrypt_json(json.loads(STORE.read_text(encoding="utf-8")), password)
        except Exception as e:
            print(f"Kunde inte läsa/dekryptera befintlig store ({e}). Kör full synk.")
            store = {"emails": [], "last_sync": 0}

    by_id = {e["id"]: e for e in store.get("emails", [])}
    bootstrap = not by_id

    ids_to_fetch = list_message_ids(service, limit=0 if bootstrap else RECENT_LIMIT)
    print(f"{'Full' if bootstrap else 'Inkrementell'} synk: uppdaterar {len(ids_to_fetch)} mejl "
          f"(totalt {len(by_id)} kända sedan innan).")

    updated = 0
    for i, mid in enumerate(ids_to_fetch, 1):
        try:
            by_id[mid] = fetch_message(service, mid, account)
            updated += 1
        except HttpError as e:
            print(f"Google API-fel för {mid}: {e}")
        if i % 25 == 0 or i == len(ids_to_fetch):
            print(f"  {i}/{len(ids_to_fetch)}")

    store = {"emails": list(by_id.values()), "last_sync": int(time.time())}
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(
        json.dumps(encrypt_json(store, password), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Klart: {updated} mejl uppdaterade, {len(store['emails'])} totalt i store.enc.json.")


if __name__ == "__main__":
    raise SystemExit(main())
