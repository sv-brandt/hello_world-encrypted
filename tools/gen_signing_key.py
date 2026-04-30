#!/usr/bin/env python3
"""
Einmalig aufrufen: python tools/gen_signing_key.py

Erzeugt:
  signing_key.pem         - privater ECDSA-P256 Schluessel (NICHT in Git!)
  signing_key_digest.bin  - 32-Byte Public-Key-Digest (fuer eFuse, Produktion)

Kein C-Header mehr noetig: Der Trust-Anker wird zur Laufzeit aus dem
Sig-Block der laufenden Partition extrahiert (Self-Reference, wie ESP-IDF).

WICHTIG: signing_key.pem ist der einzige Vertrauensanker. Backupen.
"""
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = os.path.join(PROJECT_ROOT, "signing_key.pem")
DIGEST = os.path.join(PROJECT_ROOT, "signing_key_digest.bin")


def run_espsecure(args):
    """espsecure aufrufen, mit Fallback auf 'python -m espsecure'."""
    try:
        return subprocess.run(["espsecure"] + args, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return subprocess.run([sys.executable, "-m", "espsecure"] + args, check=True)


if os.path.exists(KEY):
    print(f"FEHLER: {KEY} existiert bereits.")
    print("Bewusst loeschen, falls neu generieren gewollt.")
    print("ACHTUNG: Neuer Schluessel = alle bisher signierten Bins ungueltig.")
    print("         Bei Self-Reference: Geraete mit altem Key akzeptieren neuen Key NICHT.")
    print("         Migration nur ueber Zwischenversion mit beiden Schluesseln moeglich.")
    sys.exit(1)

# 1. ECDSA-P256-Key generieren
run_espsecure(["generate_signing_key", "--version", "2",
               "--scheme", "ecdsa256", KEY])

# 2. Digest fuer eFuse erzeugen (fuer spaeteren HW-SB-Schritt)
run_espsecure(["digest_sbv2_public_key", "--keyfile", KEY,
               "--output", DIGEST])

digest = open(DIGEST, "rb").read()
if len(digest) != 32:
    print(f"FEHLER: Digest hat {len(digest)} Bytes, erwartet 32.")
    sys.exit(1)

print(f"\nOK. Digest: {digest.hex()}")
print(f"  {KEY}")
print(f"     -> JETZT BACKUPEN (mind. 2 sichere Orte). Nicht in Git committen!")
print(f"  {DIGEST}")
print(f"     -> fuer spaetere eFuse-Brennung (Produktion).")