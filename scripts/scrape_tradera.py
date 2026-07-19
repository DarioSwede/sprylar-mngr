#!/usr/bin/env python3
"""Skrapar säljarens publika Tradera-profil (aktiva annonser: pris, bud, sluttid).

Ingen inloggning behövs — Traderas profilsida är serverrenderad och all
data för de aktiva annonserna ligger redan i sidans __NEXT_DATA__-JSON,
under props.pageProps.initialState.discover.items.

Miljövariabler (valfria):
  TRADERA_MEMBER_ID (default 5045467)
  TRADERA_ALIAS     (default darioswede)
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from pathlib import Path

MEMBER_ID = os.environ.get("TRADERA_MEMBER_ID", "5045467")
ALIAS = os.environ.get("TRADERA_ALIAS", "darioswede")
BASE_URL = f"https://www.tradera.com/profile/items/{MEMBER_ID}/{ALIAS}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")
BASE = Path(__file__).resolve().parent.parent
STORE = BASE / "data" / "store.json"


def fetch_discover(page: int) -> dict:
    url = BASE_URL if page == 1 else f"{BASE_URL}?page={page}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode("utf-8", errors="replace")
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError("Hittade inte __NEXT_DATA__ i Tradera-sidan (layouten kan ha ändrats).")
    data = json.loads(m.group(1))
    return data["props"]["pageProps"]["initialState"]["discover"]


def fetch_all_items() -> list[dict]:
    # OBS: Traderas ?page=N-parameter paginerar inte tillförlitligt för den
    # här profilvyn — den kan returnera samma (eller en omblandad delmängd
    # av samma) annonser istället för nästa sida. Vi dedupar därför på
    # itemId medan vi hämtar, så att sådana överlapp aldrig ger dubbletter
    # i store.json.
    discover = fetch_discover(1)
    items = list(discover.get("items") or [])
    seen = {it.get("itemId") for it in items}
    page_count = (discover.get("pagination") or {}).get("pageCount", 1)
    for p in range(2, page_count + 1):
        time.sleep(1)
        discover = fetch_discover(p)
        for it in discover.get("items") or []:
            if it.get("itemId") not in seen:
                seen.add(it.get("itemId"))
                items.append(it)
    return items


def simplify(item: dict) -> dict:
    return {
        "id": item.get("itemId"),
        "title": item.get("shortDescription", ""),
        "price": item.get("price", 0),
        "buy_now_price": item.get("buyNowPrice", 0),
        "bids": item.get("totalBids", 0),
        "item_type": item.get("itemType", ""),
        "start_date": item.get("startDate", ""),
        "end_date": item.get("endDate", ""),
        "url": item.get("itemUrl", ""),
        "image": (item.get("imageUrlTemplate") or "").replace("{format}", "small-square"),
    }


def main():
    items = fetch_all_items()
    by_id = {}
    for it in (simplify(i) for i in items):
        by_id[it["id"]] = it
    listings = sorted(by_id.values(), key=lambda x: x["end_date"])

    store = {}
    if STORE.exists():
        try:
            store = json.loads(STORE.read_text(encoding="utf-8"))
        except Exception:
            store = {}

    # Bilder sparas permanent per objekt-id, så miniatyren finns kvar även
    # efter att varan sålts och försvunnit från de aktiva annonserna.
    images = store.get("item_images", {})
    for it in listings:
        if it["image"]:
            images[str(it["id"])] = it["image"]

    store["listings"] = listings
    store["listings_synced_at"] = int(time.time())
    store["item_images"] = images

    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Klart: {len(listings)} aktiva annonser sparade i store.json.")


if __name__ == "__main__":
    raise SystemExit(main())
