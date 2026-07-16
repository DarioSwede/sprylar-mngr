#!/usr/bin/env python3
"""Importerar en Tradera-utbetalningsrapport (CSV, exporterad manuellt från
"Mina sidor -> Ekonomi") och slår ihop verklig provision/fraktavgift per
order i data/store.json, som ersätter gissningen (10% schablon) i frontend.

Körs manuellt lokalt när du laddat ner en ny rapport, INTE av GitHub Action:en
(Tradera kräver inloggning för den sidan, går inte att skrapa automatiskt).

Användning:
  python3 scripts/import_payouts.py /sökväg/till/utbetalningar.csv
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
STORE = BASE / "data" / "store.json"


def sek(v: str) -> float:
    v = (v or "").strip().replace("\xa0", "").replace(" ", "")
    if not v:
        return 0.0
    return float(v.replace(",", "."))


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Användning: python3 scripts/import_payouts.py <csv-fil>")
    csv_path = Path(sys.argv[1]).expanduser()

    ledger: dict[str, dict] = {}
    with csv_path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f, delimiter=";"):
            order = (row.get("Ordernummer") or "").strip()
            if not order:
                continue
            entry = ledger.setdefault(order, {"sale": 0.0, "shipping": 0.0, "commission": 0.0})
            event = row.get("Händelse", "")
            text = row.get("Text", "")
            amount = sek(row.get("Pris totalt", ""))
            if event == "Inbetalning":
                if text.startswith("Frakt"):
                    entry["shipping"] += amount
                else:
                    entry["sale"] += amount
            elif event == "Provision":
                entry["commission"] += abs(amount)

    store = json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else {}
    store["order_ledger"] = ledger
    STORE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Klart: {len(ledger)} order importerade från {csv_path.name} till order_ledger.")


if __name__ == "__main__":
    main()
