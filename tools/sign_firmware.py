"""
Post-Build Script: signiert firmware.bin per espsecure fuer Secure Boot v2.
Originale Firmware wird in unsigned-firmware.bin umbenannt. 
Signierte Firmware wird als firmware.bin gespeichert fuer Auto-Flash.

Voraussetzung: signing_key.pem im Projekt-Root (via tools/gen_signing_key.py).
und "pip install esptool"
"""
Import("env")
import os
import subprocess
import sys
import importlib.util

def check_and_install_esptool():
    """Prüft, ob esptool installiert ist, und installiert es falls nötig."""
    if importlib.util.find_spec("esptool") is None:
        print("[PRE-BUILD] 'esptool' nicht gefunden. Installiere...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "esptool"])
            print("[PRE-BUILD] Installation erfolgreich.")
        except Exception as e:
            print(f"[PRE-BUILD] FEHLER: Installation fehlgeschlagen: {e}")
            sys.exit(1)

# Sofortige Prüfung beim Laden des Scripts
check_and_install_esptool()

def sign_firmware_sbv2(source, target, env):
    firmware_path = str(target[0])
    if not firmware_path.endswith(".bin"):
        print(f"[OTA SIGN] FEHLER: Pfad endet nicht auf .bin: {firmware_path}")
        sys.exit(1)
    
    dir_name = os.path.dirname(firmware_path)
    base_name = os.path.basename(firmware_path)
    
    # Pfad für die unsignierte Datei definieren
    unsigned_path = os.path.join(dir_name, "unsigned-" + base_name)
    key_path = os.path.join(env.subst("$PROJECT_DIR"), "signing_key.pem")

    if not os.path.isfile(key_path):
        print("[OTA SIGN] FEHLER: signing_key.pem fehlt. "
              "Erst 'python tools/gen_signing_key.py' ausfuehren.")
        sys.exit(1)

    # 1. Originaldatei umbenennen (firmware.bin -> unsigned-firmware.bin)
    os.replace(firmware_path, unsigned_path)

    # 2. Signieren (liest unsigned, gibt unter originalem firmware.bin Pfad aus)
    cmd = [
        "espsecure", "sign_data", "--version", "2",
        "--keyfile", key_path,
        "--output", firmware_path,
        unsigned_path,
    ]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        # Fallback: Falls 'espsecure' nicht im PATH, aber als Modul installierbar ist
        subprocess.run([sys.executable, "-m", "espsecure"] + cmd[1:], check=True)

    print(f"[OTA SIGN] OK: {os.path.basename(firmware_path)} "
          f"({os.path.getsize(firmware_path)} Bytes, signiert)")

env.AddPostAction("$BUILD_DIR/${PROGNAME}.bin", sign_firmware_sbv2)