#!/usr/bin/env python3
"""
Einmalig aufrufen: python tools/gen_signing_key.py
Erzeugt signing_key.pem (Secure Boot v2 kompatibel via espsecure.py)
und schreibt den oeffentlichen Schluessel nach include/ota_signing_key.h.
signing_key.pem NIEMALS einchecken!
"""
import os
import sys
import subprocess

KEY_PATH = "signing_key.pem"
HEADER_PATH = os.path.join("include", "ota_signing_key.h")


def main():
    if os.path.exists(KEY_PATH):
        print(f"FEHLER: {KEY_PATH} existiert bereits. Loeschen falls Neugenerierung gewuenscht.")
        sys.exit(1)

    # Schluessel generieren – espsecure.py bevorzugt (Secure Boot v2 Format)
    try:
        subprocess.run(
            ["espsecure.py", "generate_signing_key",
             "--version", "2", "--scheme", "ecdsa256", KEY_PATH],
            check=True
        )
        print(f"Schluessel via espsecure.py erstellt: {KEY_PATH}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: cryptography-Bibliothek (in PlatformIO-Python enthalten)
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        priv = ec.generate_private_key(ec.SECP256R1())
        with open(KEY_PATH, "wb") as f:
            f.write(priv.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            ))
        print(f"Schluessel via cryptography-Lib erstellt: {KEY_PATH}")

    # Oeffentlichen Schluessel als DER extrahieren
    from cryptography.hazmat.primitives import serialization
    with open(KEY_PATH, "rb") as f:
        priv = serialization.load_pem_private_key(f.read(), password=None)
    pub_der = priv.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Header schreiben
    hex_bytes = ", ".join(f"0x{b:02x}" for b in pub_der)
    header = (
        "#pragma once\n"
        "#include <stdint.h>\n\n"
        "// OTA-Signaturschluessel (ECDSA-P256, DER-kodiert, SubjectPublicKeyInfo)\n"
        "// Generiert mit: python tools/gen_signing_key.py\n"
        f"static const uint8_t OTA_PUBLIC_KEY_DER[{len(pub_der)}] = {{\n"
        f"    {hex_bytes}\n"
        "};\n"
        f"static const size_t OTA_PUBLIC_KEY_DER_LEN = {len(pub_der)};\n"
    )
    with open(HEADER_PATH, "w") as f:
        f.write(header)

    print(f"Oeffentlicher Schluessel ({len(pub_der)} Bytes) -> {HEADER_PATH}")
    print(f"WICHTIG: {KEY_PATH} ist in .gitignore – niemals einchecken!")


if __name__ == "__main__":
    main()
