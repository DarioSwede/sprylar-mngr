#!/usr/bin/env python3
"""Extraherar fraktfält (transportbolag, spårningsnummer, QR-kod m.m.)
ur Tradera/PostNord/DHL/Schenker-mejl. Oförändrad logik från POC:ens
shipping_parser_v17.py.
"""
from __future__ import annotations
import re
from html import unescape
from typing import Any


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def compact_tracking(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def first(patterns: list[str], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.M | re.S)
        if match:
            return compact(match.group(1))
    return ""


def parse_shipping_fields(subject: str, body: str, html: str = "") -> dict[str, str]:
    line_text = f"{subject}\n{body}"
    text = compact(line_text)

    carrier = first([
        r"\b(PostNord|DHL|DB\s*Schenker|Schenker|Bring|UPS|FedEx|Instabox|Budbee)\b"
    ], text)

    service_line = first([
        r"\b((?:PostNord|DHL|DB\s*Schenker|Schenker|Bring)\s*,?\s*(?:upp\s+till|max(?:vikt)?|vikt)?\s*\d+(?:[.,]\d+)?\s*kg)\b",
        r"\b((?:PostNord|DHL|DB\s*Schenker|Schenker|Bring)[^|]{0,80})\b"
    ], text)

    weight = first([
        r"\b(?:upp\s+till|max(?:vikt)?|vikt)\s*:?\s*(\d+(?:[.,]\d+)?\s*kg)\b",
        r"\b(\d+(?:[.,]\d+)?\s*kg)\b"
    ], text)

    package_size = first([
        r"\b(Medium|Small|Large|Liten|Mellan|Stor)\b"
    ], text)

    dimensions = first([
        r"\b((?:Max\s*)?\d+\s*[x×]\s*\d+\s*[x×]\s*\d+\s*cm)\b"
    ], text)

    pickup = first([
        r"Närmaste\s+ombud\s*:?\s*(.+?)(?=\s+(?:Spårningsnr|Sändningsnummer|Kollinummer|Ladda\s+ner|$))",
        r"\bOmbud\s*:?\s*(.+?)(?=\s+(?:Spårningsnr|Sändningsnummer|Kollinummer|$))"
    ], text)

    # Character class utan \s: en spårningskod är alltid en sammanhängande
    # sträng, så regexen ska stanna vid första blanksteg/radbrytning efter
    # etiketten istället för att glupskt äta text över flera rader (t.ex.
    # mottagarens namn och adress i DHL/PostNord-mejl).
    tracking_raw = first([
        r"Spårningsnr\.?\s*:?\s*([A-Z0-9][A-Z0-9\-]{5,39})",
        r"Sändningsnummer\s*:?\s*([A-Z0-9][A-Z0-9\-]{5,39})",
        r"Kollinummer\s*:?\s*([A-Z0-9][A-Z0-9\-]{5,39})"
    ], line_text)
    tracking = compact_tracking(tracking_raw)
    if len(tracking) > 40:
        tracking = tracking[:40]
    if len(tracking) < 10:
        tracking = ""

    return {
        "shipping_carrier": carrier,
        "shipping_service": service_line,
        "shipping_weight": weight,
        "shipping_pickup": pickup,
        "tracking_number": tracking,
        "package_dimensions": dimensions,
        "package_size": package_size,
    }


def extract_remote_images(html: str) -> list[dict[str, Any]]:
    images = []
    for match in re.finditer(r"(?is)<img\b([^>]+)>", html or ""):
        attrs = match.group(1)
        src_match = re.search(r"src\s*=\s*[\"']([^\"']+)[\"']", attrs, re.I)
        if not src_match:
            continue
        src = unescape(src_match.group(1))
        if not src.startswith(("http://", "https://", "data:image/")):
            continue

        width = 0
        height = 0
        wm = re.search(r"width\s*=\s*[\"']?(\d+)", attrs, re.I)
        hm = re.search(r"height\s*=\s*[\"']?(\d+)", attrs, re.I)
        if wm:
            width = int(wm.group(1))
        if hm:
            height = int(hm.group(1))

        style = re.search(r"style\s*=\s*[\"']([^\"']+)[\"']", attrs, re.I)
        if style:
            if not width:
                m = re.search(r"width\s*:\s*(\d+)px", style.group(1), re.I)
                if m:
                    width = int(m.group(1))
            if not height:
                m = re.search(r"height\s*:\s*(\d+)px", style.group(1), re.I)
                if m:
                    height = int(m.group(1))

        alt = ""
        am = re.search(r"alt\s*=\s*[\"']([^\"']*)[\"']", attrs, re.I)
        if am:
            alt = unescape(am.group(1))

        images.append({"src": src, "width": width, "height": height, "alt": alt, "tag": match.group(0)})
    return images


def choose_qr_image(embedded_images: list[dict[str, Any]], html: str) -> str:
    candidates: list[tuple[float, str]] = []

    for image in embedded_images or []:
        width = int(image.get("width") or 0)
        height = int(image.get("height") or 0)
        name = f"{image.get('filename','')} {image.get('content_id','')}".lower()
        source = image.get("data_url", "")
        if not source:
            continue
        score = 0.0
        if "qr" in name or "barcode" in name:
            score += 1500
        if width and height:
            ratio = min(width, height) / max(width, height)
            score += ratio * 800
            if 120 <= width <= 800 and 120 <= height <= 800:
                score += 300
        candidates.append((score, source))

    for image in extract_remote_images(html):
        width = image["width"]
        height = image["height"]
        descriptor = f"{image['src']} {image['alt']} {image['tag']}".lower()
        score = 0.0
        if "qr" in descriptor or "barcode" in descriptor:
            score += 1600
        if width and height:
            ratio = min(width, height) / max(width, height)
            score += ratio * 900
            if 120 <= width <= 800 and 120 <= height <= 800:
                score += 350
            if ratio < 0.75:
                score -= 500
        else:
            score += 50
        candidates.append((score, image["src"]))

    return max(candidates, key=lambda item: item[0])[1] if candidates else ""
