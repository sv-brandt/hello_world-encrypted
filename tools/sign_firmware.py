Import("env")
import os
import sys

try:
    import cryptography
except ImportError:
    print("[OTA SIGN] 'cryptography' fehlt. Installiere Paket in PIO-Umgebung...")
    env.Execute("$PYTHONEXE -m pip install cryptography")

def sign_firmware(source, target, env):
    firmware_path = str(target[0])
    sig_path = firmware_path + ".sig"
    project_dir = env.subst("$PROJECT_DIR")
    key_path = os.path.join(project_dir, "signing_key.pem")

    if not os.path.isfile(key_path):
        print("[OTA SIGN] signing_key.pem nicht gefunden – Firmware NICHT signiert.")
        print("           -> python tools/gen_signing_key.py ausfuehren")
        return

    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec, rsa, padding as asym_padding

        with open(key_path, "rb") as f:
            priv = serialization.load_pem_private_key(f.read(), password=None)

        with open(firmware_path, "rb") as f:
            firmware_data = f.read()

        if isinstance(priv, rsa.RSAPrivateKey):
            # RSA-PKCS1v15 (Secure Boot v2 RSA-Scheme)
            signature = priv.sign(firmware_data, asym_padding.PKCS1v15(), hashes.SHA256())
        else:
            # ECDSA-P256 ueber SHA-256, DER-kodierte Ausgabe
            signature = priv.sign(firmware_data, ec.ECDSA(hashes.SHA256()))

        with open(sig_path, "wb") as f:
            f.write(signature)

        print(f"[OTA SIGN] {os.path.basename(sig_path)} ({len(signature)} Bytes) erstellt")

    except Exception as e:
        print(f"[OTA SIGN] FEHLER: {e}")
        sys.exit(1)


env.AddPostAction("$BUILD_DIR/${PROGNAME}.bin", sign_firmware)
