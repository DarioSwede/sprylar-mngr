"""Symmetriskt krypteringslager delat mellan sync-skriptet (Python) och
frontend (WebCrypto i assets/app.js). Parametrarna MÅSTE vara identiska
på båda sidor:

  PBKDF2-HMAC-SHA256, 210 000 iterationer -> AES-256-GCM
  slumpmässigt 16-byte salt + 12-byte IV per kryptering, base64-kodat.

Ändra du något här måste motsvarande värden ändras i assets/app.js.
"""
from __future__ import annotations

import base64
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITERATIONS = 210_000
KEY_LEN = 32  # 256 bitar
SALT_LEN = 16
IV_LEN = 12


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LEN,
        salt=salt,
        iterations=ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_json(payload: dict, password: str) -> dict:
    salt = os.urandom(SALT_LEN)
    iv = os.urandom(IV_LEN)
    key = _derive_key(password, salt)
    plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(iv, plaintext, None)
    return {
        "v": 1,
        "kdf": "PBKDF2-SHA256",
        "iterations": ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "iv": base64.b64encode(iv).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def decrypt_json(blob: dict, password: str) -> dict:
    salt = base64.b64decode(blob["salt"])
    iv = base64.b64decode(blob["iv"])
    ciphertext = base64.b64decode(blob["ciphertext"])
    key = _derive_key(password, salt)
    plaintext = AESGCM(key).decrypt(iv, ciphertext, None)
    return json.loads(plaintext.decode("utf-8"))
