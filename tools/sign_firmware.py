Import("env")
import os
import sys

try:
    import cryptography
except ImportError:
    env.Execute("$PYTHONEXE -m pip install cryptography")

def sign_firmware(source, target, env):
    firmware_path = str(target[0])
    signed_path = firmware_path.replace(".bin", "-signed.bin")
    project_dir = env.subst("$PROJECT_DIR")
    key_path = os.path.join(project_dir, "signing_key.pem")

    if not os.path.isfile(key_path):
        print("[OTA SIGN] signing_key.pem nicht gefunden.")
        return

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    with open(key_path, "rb") as f:
        priv = serialization.load_pem_private_key(f.read(), password=None)

    with open(firmware_path, "rb") as f:
        firmware_data = f.read()

    # ECDSA-P256 Signatur erstellen
    signature = priv.sign(firmware_data, ec.ECDSA(hashes.SHA256()))

    # Auf exakt 256 Bytes auffuellen (Padding)
    padded_signature = signature.ljust(256, b'\x00')

    # Firmware + Signatur-Block in eine Datei schreiben
    with open(signed_path, "wb") as f:
        f.write(firmware_data)
        f.write(padded_signature)

    print(f"[OTA SIGN] Appended Signature erstellt (256 Bytes Block angehaengt): {os.path.basename(signed_path)}")

env.AddPostAction("$BUILD_DIR/${PROGNAME}.bin", sign_firmware)