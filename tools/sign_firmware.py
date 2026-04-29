Import("env")
import os
import subprocess
import sys
import importlib.util

def check_and_install_esptool():
    if importlib.util.find_spec("esptool") is None:
        print("[PRE-BUILD] 'esptool' nicht gefunden. Installiere...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "esptool"])
        except Exception as e:
            print(f"[PRE-BUILD] FEHLER: {e}")
            sys.exit(1)

check_and_install_esptool()

def generate_ota_header(key_path, header_path):
    """Extrahiert den Public Key und schreibt ihn in ota_signing_key.h"""
    from cryptography.hazmat.primitives import serialization
    
    if not os.path.exists(key_path):
        return # Key noch nicht da, Header-Erzeugung überspringen

    with open(key_path, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)
        public_key = private_key.public_key()
        
        # In DER-Format exportieren (SubjectPublicKeyInfo)
        der_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    # C-Header Inhalt erstellen
    hex_values = ", ".join([f"0x{b:02x}" for b in der_bytes])
    formatted_hex = "\n    ".join([hex_values[i:i+75] for i in range(0, len(hex_values), 75)])

    header_content = f"""#pragma once
#include <stdint.h>

// OTA-Signaturschluessel (ECDSA-P256, DER-kodiert, SubjectPublicKeyInfo)
// Automatisch generiert vom Post-Build Script
static const uint8_t OTA_PUBLIC_KEY_DER[{len(der_bytes)}] = {{
    {formatted_hex}
}};
static const size_t OTA_PUBLIC_KEY_DER_LEN = {len(der_bytes)};
"""
    
    # NEU: Erstelle den Zielordner (z.B. 'include'), falls er nicht existiert
    os.makedirs(os.path.dirname(header_path), exist_ok=True)
    
    with open(header_path, "w") as f:
        f.write(header_content)
    print(f"[PRE-BUILD] Header generiert: {header_path}")

def sign_firmware_sbv2(source, target, env):
    firmware_path = str(target[0])
    project_dir = env.subst("$PROJECT_DIR")
    key_path = os.path.join(project_dir, "signing_key.pem")
    header_path = os.path.join(project_dir, "include", "ota_signing_key.h")

    # 1. Header vor dem Signieren aktualisieren/erstellen
    generate_ota_header(key_path, header_path)

    # 2. Signierung durchführen
    if not os.path.isfile(key_path):
        print("[OTA SIGN] FEHLER: signing_key.pem fehlt!")
        sys.exit(1)

    signed_path = firmware_path[:-4] + "-signed.bin"
    
    subprocess.run([
        sys.executable, "-m", "espsecure", "sign_data", "--version", "2",
        "--keyfile", key_path,
        "--output", signed_path,
        firmware_path,
    ], check=True)

    print(f"[OTA SIGN] OK: {os.path.basename(signed_path)}")

env.AddPostAction("$BUILD_DIR/${PROGNAME}.bin", sign_firmware_sbv2)