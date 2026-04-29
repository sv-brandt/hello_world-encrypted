"""
Post-Build Script: signiert firmware.bin per espsecure fuer Secure Boot v2.
Erzeugt firmware-signed.bin = padded_image (4 KB-aligned) + 4096-Byte Sig-Block.

Voraussetzung: signing_key.pem im Projekt-Root (via tools/gen_signing_key.py).
"""
Import("env")
import os
import subprocess
import sys


def sign_firmware_sbv2(source, target, env):
    firmware_path = str(target[0])
    if not firmware_path.endswith(".bin"):
        print(f"[OTA SIGN] FEHLER: Pfad endet nicht auf .bin: {firmware_path}")
        sys.exit(1)
    signed_path = firmware_path[:-4] + "-signed.bin"
    key_path = os.path.join(env.subst("$PROJECT_DIR"), "signing_key.pem")

    if not os.path.isfile(key_path):
        print("[OTA SIGN] FEHLER: signing_key.pem fehlt. "
              "Erst 'python tools/gen_signing_key.py' ausfuehren.")
        sys.exit(1)

    subprocess.run([
        "espsecure", "sign_data", "--version", "2",
        "--keyfile", key_path,
        "--output", signed_path,
        firmware_path,
    ], check=True)

    print(f"[OTA SIGN] OK: {os.path.basename(signed_path)} "
          f"({os.path.getsize(signed_path)} Bytes)")


env.AddPostAction("$BUILD_DIR/${PROGNAME}.bin", sign_firmware_sbv2)
