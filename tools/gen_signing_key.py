#!/usr/bin/env python3
"""
Einmalig aufrufen: python tools/gen_signing_key.py

Erzeugt:
  signing_key.pem         — privater ECDSA-P256 Schluessel (NICHT in Git!)
  signing_key_digest.bin  — 32-Byte Public-Key-Digest (fuer eFuse, Produktion)

WICHTIG: signing_key.pem ist der einzige Vertrauensanker. Backupen.

Hinweis fuer Software-SBv2: Anker zur Laufzeit ist der PubKey, der im
Sig-Block der bereits laufenden App steht — kein separater Header noetig.
Beim ersten Flash via Kabel wird die App mit dem Sig-Block geflasht und
"impft" sich damit selbst. Spaeter pruefen alle OTAs gegen diesen PubKey.
"""
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = os.path.join(PROJECT_ROOT, "signing_key.pem")
DIGEST = os.path.join(PROJECT_ROOT, "signing_key_digest.bin")


if os.path.exists(KEY):
    print(f"FEHLER: {KEY} existiert bereits.")
    print("Bewusst loeschen, falls neu generieren gewollt.")
    print("ACHTUNG: Neuer Schluessel = alle bisher signierten Bins ungueltig.")
    sys.exit(1)

subprocess.run(["espsecure", "generate_signing_key", "--version", "2",
                "--scheme", "ecdsa256", KEY], check=True)
subprocess.run(["espsecure", "digest_sbv2_public_key",
                "--keyfile", KEY, "--output", DIGEST], check=True)

digest = open(DIGEST, "rb").read()
if len(digest) != 32:
    print(f"FEHLER: Digest hat {len(digest)} Bytes, erwartet 32.")
    sys.exit(1)

print(f"\nOK. Digest: {digest.hex()}")
print(f"  {KEY}        -> JETZT BACKUPEN (mind. 2 sichere Orte)")
print(f"  {DIGEST}     -> fuer spaetere eFuse-Brennung (Produktion)")
