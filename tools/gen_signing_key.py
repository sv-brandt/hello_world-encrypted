#!/usr/bin/env python3
"""
Einmalig aufrufen: python tools/gen_signing_key.py

Erzeugt:
  signing_key.pem        — privater ECDSA-P256 Schluessel (NICHT in Git!)
  signing_key_digest.bin — 32-Byte Public-Key-Digest (fuer eFuse, Produktion)
  ota_signing_key.h      — C-Header mit dem Public Key im DER-Format fuer Arduino

WICHTIG: signing_key.pem ist der einzige Vertrauensanker. Backupen.
"""
import os
import subprocess
import sys

# Pruefen, ob cryptography installiert ist (wird von esptool genutzt)
try:
    from cryptography.hazmat.primitives import serialization
except ImportError:
    print("FEHLER: 'cryptography' Modul fehlt. Bitte 'pip install cryptography' ausfuehren.")
    sys.exit(1)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = os.path.join(PROJECT_ROOT, "signing_key.pem")
DIGEST = os.path.join(PROJECT_ROOT, "signing_key_digest.bin")
HEADER_DIR = os.path.join(PROJECT_ROOT, "include")
HEADER_FILE = os.path.join(HEADER_DIR, "ota_signing_key.h")

if os.path.exists(KEY):
    print(f"FEHLER: {KEY} existiert bereits.")
    print("Bewusst loeschen, falls neu generieren gewollt.")
    print("ACHTUNG: Neuer Schluessel = alle bisher signierten Bins ungueltig.")
    sys.exit(1)

# 1. Key generieren
subprocess.run(["espsecure", "generate_signing_key", "--version", "2",
                "--scheme", "ecdsa256", KEY], check=True)

# 2. Digest generieren
subprocess.run(["espsecure", "digest_sbv2_public_key",
                "--keyfile", KEY, "--output", DIGEST], check=True)

digest = open(DIGEST, "rb").read()
if len(digest) != 32:
    print(f"FEHLER: Digest hat {len(digest)} Bytes, erwartet 32.")
    sys.exit(1)

# 3. Public Key extrahieren und C-Header generieren
with open(KEY, "rb") as f:
    private_key = serialization.load_pem_private_key(f.read(), password=None)
    public_key = private_key.public_key()
    
    der_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

hex_values = ", ".join([f"0x{b:02x}" for b in der_bytes])
formatted_hex = "\n    ".join([hex_values[i:i+75] for i in range(0, len(hex_values), 75)])

header_content = f"""#pragma once
#include <stdint.h>

// OTA-Signaturschluessel (ECDSA-P256, DER-kodiert, SubjectPublicKeyInfo)
// Automatisch generiert von tools/gen_signing_key.py
static const uint8_t OTA_PUBLIC_KEY_DER[{len(der_bytes)}] = {{
    {formatted_hex}
}};
static const size_t OTA_PUBLIC_KEY_DER_LEN = {len(der_bytes)};
"""

os.makedirs(HEADER_DIR, exist_ok=True)
with open(HEADER_FILE, "w") as f:
    f.write(header_content)

# 4. Abschlussausgabe
print(f"\nOK. Digest: {digest.hex()}")
print(f"  {KEY}        -> JETZT BACKUPEN (mind. 2 sichere Orte)")
print(f"  {DIGEST} -> fuer spaetere eFuse-Brennung (Produktion)")
print(f"  {HEADER_FILE} -> C-Header fuer Arduino-Code")