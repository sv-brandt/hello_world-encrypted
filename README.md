# Dokumentation: Secure Boot v2 Signierungspipeline & espsecure verify_signature

Unser Build-System setzt auf zwei Python-Scripts in `/tools`. Dieses Hello-World-Projekt (ESP32-C6, Arduino/PlatformIO, 4 MB Flash) dient als öffentlich verfügbare Test-Firmware, um die OTA-Signierungspipeline für unsere eigentliche Produktionsfirmware zu validieren. Es werden keine eFuses gesetzt — alles bleibt reversibel.

---

## Architektur (Testmodus)

| Komponente | Status |
|---|---|
| Secure Boot (eFuse-Hardware-Lock) | **NICHT aktiv** |
| Signaturprüfung | Host-seitig vor dem Flashen via `espsecure verify_signature` |
| OTA | aktiv — diese Firmware dient als OTA-Quelle, nicht als OTA-Client |
| Flash Encryption | nicht aktiviert |

> **Wichtig:** Echtes Secure Boot mit eFuse-Brennung ist **irreversibel**. In dieser Testphase werden keine eFuses gesetzt. Das Gerät ist jederzeit durch vollständiges Reflashen zurücksetzbar: `esptool.py erase_flash`

---

## Schlüsselschema

Für Secure Boot v2 wird **ECDSA-P256** (kurz: ECDSA-256) verwendet — der Algorithmus unserer Produktion.

**RSA-3072** existiert als Überbleibsel früherer Tests. Die Ordner bleiben im Repository als Referenz für eventuelle zukünftige RSA-Tests.

> **Achtung:** Die `signing_key.pem`-Dateien in den Testordnern sind Wegwerfschlüssel, die bewusst committed wurden. Sie dürfen unter keinen Umständen in der Produktion verwendet werden.

---

## Partition Table

Die Partition Table dieser Test-Firmware muss identisch mit der Partition Table der Zielfirmware sein, auf welcher die OTA-Updates durchgeführt werden. Eine abweichende Partition Table führt zu inkompatiblen Partition-Offsets und macht OTA-Updates unzuverlässig.

---

## Tools

### `tools/gen_signing_key.py` — Schlüsselgenerator

Einmalig aufrufen, bevor erstmals eine Firmware signiert wird:

```bash
python tools/gen_signing_key.py
```

Erzeugt zwei Dateien im Projekt-Root:

| Datei | Inhalt | Verwendung |
|---|---|---|
| `signing_key.pem` | Privater ECDSA-P256-Schlüssel | Signieren der Firmware |
| `signing_key_digest.bin` | SHA-256-Digest des Public Keys (32 Byte) | eFuse-Brennung in Produktion |

**Ablauf:**
1. Prüft, ob `signing_key.pem` bereits existiert — bricht ab, falls ja.
2. Ruft `espsecure generate_signing_key --version 2 --scheme ecdsa256` auf.
3. Ruft `espsecure digest_sbv2_public_key` auf und validiert die Ausgabe auf 32 Byte.

> `signing_key.pem` ist der einzige Vertrauensanker — **sofort an mindestens zwei sicheren Orten sichern** und nicht in Git committen. Ein neuer Schlüssel macht alle bisher signierten Binaries ungültig. Geräte mit gebranntem eFuse (Produktion) akzeptieren einen anderen Key nur über eine Zwischenversion mit beiden Schlüsseln.

#### Private Key, Public Key und Digest

`signing_key.pem` enthält im PEM-Format sowohl den privaten als auch den öffentlichen Schlüssel. Das ist bei ECDSA-Schlüsseln Standard: Der Public Key ist der aus dem Private Key mathematisch abgeleitete Punkt auf der elliptischen Kurve (`public = private × G`) und wird zur Vereinfachung in derselben Datei gespeichert.

Den Public Key separat exportieren:

```bash
espsecure.py extract_public_key --version 2 --keyfile signing_key.pem public_key.pem
```

`public_key.pem` enthält den EC-Public-Key (P-256) im PEM-Format und kann ohne Sicherheitsbedenken weitergegeben werden — der Private Key lässt sich daraus nicht ableiten.

| | `public_key.pem` | `signing_key_digest.bin` |
|---|---|---|
| Inhalt | EC-Public-Key (P-256), PEM-Format | SHA-256-Hash des Public Keys, 32 Byte binär |
| Verwendung | Host-seitige Signaturprüfung | eFuse-Brennung (Produktion) |

**Warum wir nur den Digest brauchen:** Der ESP32-Bootloader speichert im eFuse nicht den vollständigen Public Key, sondern nur dessen 32-Byte-SHA-256-Hash. Beim Booten extrahiert er den Public Key aus dem Signatur-Block der Firmware, hasht ihn und vergleicht mit dem eFuse-Wert. Der Public Key steckt also bereits in der signierten `firmware.bin` — er muss dem Gerät nie separat übergeben werden.

In unserer Testumgebung (ohne eFuse) entfällt dieser Vergleich vollständig. `verify_signature` auf dem Host arbeitet direkt mit `signing_key.pem`. (Wir haben auch eine Ota_verify Klasse im Gateway Projekt, welche dies kann, vorraussichtlich werden wir diese aber aufgrund ihrer Komplexität verwerfen.)

---

### `tools/sign_firmware.py` — Post-Build-Signierschritt

Wird automatisch von PlatformIO nach jedem Build aufgerufen (`extra_scripts = post:tools/sign_firmware.py` in `platformio.ini`). Kein manueller Aufruf nötig.

**Ablauf:**
1. Prüft, ob `esptool` installiert ist; installiert es via `pip` falls nötig.
2. Prüft, ob `signing_key.pem` im Projekt-Root vorhanden ist.
3. Benennt `firmware.bin` um in `unsigned-firmware.bin`.
4. Signiert `unsigned-firmware.bin` mit folgendem Befehl und speichert das Ergebnis als `firmware.bin`:

```bash
espsecure sign_data \
  --version 2 \
  --keyfile signing_key.pem \
  --output firmware.bin \
  unsigned-firmware.bin
```

| Parameter | Bedeutung |
|---|---|
| `--version 2` | Secure Boot v2 (für ESP32-C6 erforderlich) |
| `--keyfile` | Privater ECDSA-P256-Schlüssel |
| `--output` | Ausgabedatei (signierte Firmware) |
| (letztes Argument) | Eingabedatei (unsignierte Firmware) |

| Datei | Inhalt |
|---|---|
| `unsigned-firmware.bin` | Unsignierte Firmware |
| `firmware.bin` | Signierte Firmware (Secure Boot v2 kompatibel) |

Bei fehlendem `espsecure` im PATH greift ein Fallback auf `python -m espsecure`.

---

## `espsecure verify_signature` — Manuelle Signaturprüfung

Nicht im Build-Workflow integriert. Der Befehl wird manuell auf dem Host ausgeführt, um zu prüfen, ob eine `.bin`-Datei korrekt mit einem bestimmten Schlüssel signiert ist.

```bash
espsecure verify_signature \
  --version 2 \
  --keyfile signing_key.pem \
  firmware.bin
```

| Parameter | Bedeutung |
|---|---|
| `--version 2` | Secure Boot v2 (für ESP32-C6 erforderlich) |
| `--keyfile` | Privater oder öffentlicher Key |
| (letztes Argument) | Zu prüfende `.bin`-Datei |

```
Signature is valid        # Gültige Signatur
Signature is NOT valid    # Falscher Key oder manipulierte Datei
```

Typische Verwendung: Vor OTA-Upload prüfen, Negativtests nachvollziehen, Debugging.

---

## Testfälle — Ordnerstruktur

Jeder Testordner enthält: `signing_key.pem`, `signing_key_digest.bin`, `unsigned-firmware.bin`, `firmware.bin`.

### ECDSA-256 Testfälle

| Ordner | Schlüssel | Firmware | Erwartetes Ergebnis |
|---|---|---|---|
| `securebootv2_first_ECDSA-256` | Key A | gültig signiert | ✅ gültig |
| `securebootv2_second_ECDSA-256` | Key B | gültig signiert | ❌ falscher Key |
| `securebootv2_first_ECDSA-256_hacked` | Key A | manipuliert¹ | ❌ Dateigröße ungültig |
| `securebootv2_second_ECDSA-256_hacked` | Key B | manipuliert¹ | ❌ Dateigröße ungültig |
| `securebootv2_first_ECDSA-256_bytechange` | Key A | manipuliert² | ❌ Digest mismatch |
| `securebootv2_second_ECDSA-256_bytechange` | Key B | manipuliert² | ❌ Digest mismatch |

<details>
  <summary>Konsolenausgabe</summary>

```
(venv) PS E:\google_drive\Werkstudentenjob\Projekte\hello_world-encrypted> espsecure verify_signature --version 2 --keyfile securebootv2_first_ECDSA-256/signing_key.pem securebootv2_first_ECDSA-256/firmware.bin
espsecure.py v4.12.dev1
Signature block 0 is valid (ECDSA).
Signature block 0 verification successful using the supplied key (ECDSA).
Signature block 1 invalid. Skipping.
Signature block 2 invalid. Skipping.
(venv) PS E:\google_drive\Werkstudentenjob\Projekte\hello_world-encrypted> espsecure verify_signature --version 2 --keyfile securebootv2_first_ECDSA-256/signing_key.pem securebootv2_second_ECDSA-256/firmware.bin
espsecure.py v4.12.dev1
Signature block 0 is valid (ECDSA).
Signature block 0 is not signed by the supplied key. Checking the next block
Signature block 1 invalid. Skipping.
Signature block 2 invalid. Skipping.

A fatal error occurred: Checked all blocks. Signature could not be verified with the provided key.
(venv) PS E:\google_drive\Werkstudentenjob\Projekte\hello_world-encrypted> espsecure verify_signature --version 2 --keyfile securebootv2_first_ECDSA-256_hacked/signing_key.pem securebootv2_first_ECDSA-256_hacked/firmware.bin
espsecure.py v4.12.dev1

A fatal error occurred: Invalid datafile. Data size should be non-zero & a multiple of 4096.
(venv) PS E:\google_drive\Werkstudentenjob\Projekte\hello_world-encrypted> espsecure verify_signature --version 2 --keyfile securebootv2_first_ECDSA-256_hacked/signing_key.pem securebootv2_second_ECDSA-256_hacked/firmware.bin
espsecure.py v4.12.dev1

A fatal error occurred: Invalid datafile. Data size should be non-zero & a multiple of 4096.
(venv) PS E:\google_drive\Werkstudentenjob\Projekte\hello_world-encrypted> espsecure verify_signature --version 2 --keyfile securebootv2_first_ECDSA-256_bytechange/signing_key.pem securebootv2_first_ECDSA-256_bytechange/firmware.bin
espsecure.py v4.12.dev1
Signature block 0 is valid (ECDSA).

A fatal error occurred: Signature block image digest does not match the actual image digest b'\x849a\x16P]\x0fgX\x98\x11H\x0b\xc2\x00t\xb6\xbb0\xe8\x84o\xc3\xf5\xc9\xffGh\x9f#\xe62'. Expected b'\xa5\x96V#\x11vLg/\x01^WV\xd2i\x82\xd1\xee\xb2\xe6\xa0\xe1\x0b\x98\xefF.0\x8aWCg'.

(venv) PS E:\google_drive\Werkstudentenjob\Projekte\hello_world-encrypted> espsecure verify_signature --version 2 --keyfile securebootv2_first_ECDSA-256_bytechange/signing_key.pem securebootv2_second_ECDSA-256_bytechange/firmware.bin 
espsecure.py v4.12.dev1
Signature block 0 is valid (ECDSA).

A fatal error occurred: Signature block image digest does not match the actual image digest b'\x849a\x16P]\x0fgX\x98\x11H\x0b\xc2\x00t\xb6\xbb0\xe8\x84o\xc3\xf5\xc9\xffGh\x9f#\xe62'. Expected b'\xa5\x96V#\x11vLg/\x01^WV\xd2i\x82\xd1\xee\xb2\xe6\xa0\xe1\x0b\x98\xefF.0\x8aWCg'.
```
</details>



¹ Manipulation: `echo "hacked" >> firmware.bin` — hängt Bytes an, Dateigröße ist kein Vielfaches von 4096 mehr. espsecure prüft die Signatur nicht; der Test prüft nur Dateiformat-Validierung.

² Manipulation: XOR eines Bytes bei Offset `0x1000` — Dateigröße bleibt unverändert. espsecure verifiziert den Key erfolgreich, scheitert dann aber am Digest-Vergleich: der gespeicherte SHA-256 des Originalinhalts stimmt nicht mit dem SHA-256 des veränderten Inhalts überein.  
Python Befehl dafür:  
`python -c "f=open('securebootv2_second_ECDSA-256_bytechange/firmware.bin','r+b');f.seek(0x1000);f.write(bytes([f.read(1)[0]^0xFF]));f.close()"`

`first` und `second` enthalten dieselbe Firmware, signiert mit unterschiedlichen Keys — Negativtest für den Fall, dass eine Firmware mit einem fremden Schlüssel signiert wurde.

### RSA-3072 Testfälle (Überbleibsel, nicht produktiv)

`securebootv2_first_RSA-3072` und `securebootv2_second_RSA-3072` bleiben als Referenz für eventuelle RSA-Tests.

---

## Hinweis: Flash-Verhalten von PlatformIO

PlatformIO überschreibt beim Flashen nur die Blöcke, die die neue Firmware belegt. Blöcke der vorherigen Firmware bleiben unangetastet.

Konsequenz: Der Signatur-Block einer früheren Firmware **bleibt im Flash erhalten**, auch wenn danach eine unsignierte Firmware geflasht wird — was Negativtests verfälscht.

Vor jedem Negativtest, bei dem die Ausgangsfirmware keine Signatur haben soll:

```bash
pio run -t erase
```

Erst danach die gewünschte Firmware flashen.

---

## Negativtests — Anleitung

Die folgenden Befehle prüfen die gespeicherten Test-Binaries host-seitig via `espsecure verify_signature`.

### Test 1: Falscher Schlüssel

```bash
espsecure verify_signature \
  --version 2 \
  --keyfile securebootv2_first_ECDSA-256/signing_key.pem \
  securebootv2_second_ECDSA-256/firmware.bin
```

Erwartung: `Signature is NOT valid`

### Test 2: Ungültige Dateigröße (_hacked)

```bash
espsecure verify_signature \
  --version 2 \
  --keyfile securebootv2_first_ECDSA-256_hacked/signing_key.pem \
  securebootv2_first_ECDSA-256_hacked/firmware.bin
```

Erwartung: `Fatal error: Invalid datafile. Data size should be non-zero & a multiple of 4096` — Signaturprüfung wird nicht erreicht.

### Test 3: Manipulierter Inhalt (_bytechange, richtiger Key)

```bash
espsecure verify_signature \
  --version 2 \
  --keyfile securebootv2_first_ECDSA-256_bytechange/signing_key.pem \
  securebootv2_first_ECDSA-256_bytechange/firmware.bin
```

Erwartung: `Fatal error: Signature block image digest does not match` — Key wird erkannt, Inhalt wurde nach der Signierung verändert.

### Test 4: Manipulierter Inhalt (_bytechange, falscher Key)

```bash
espsecure verify_signature \
  --version 2 \
  --keyfile securebootv2_first_ECDSA-256_bytechange/signing_key.pem \
  securebootv2_second_ECDSA-256_bytechange/firmware.bin
```

Erwartung: `Fatal error: Signature block image digest does not match` — gleicher Fehlermodus wie Test 3.

### Test 5: Positivtest (Referenz)

```bash
espsecure verify_signature \
  --version 2 \
  --keyfile securebootv2_first_ECDSA-256/signing_key.pem \
  securebootv2_first_ECDSA-256/firmware.bin
```

Erwartung: `Signature block 0 verification successful using the supplied key (ECDSA).`

---

## Testergebnisse

| Testfall | Erwartetes Ergebnis | Tatsächliches Ergebnis | Datum |
|---|---|---|---|
| Positivtest (first, Key A) | ✅ Signatur gültig | ✅ `Signature block 0 verification successful` | 2026-05-06 |
| Negativtest falscher Key (second mit Key A) | ❌ Key passt nicht | ❌ `Checked all blocks. Signature could not be verified with the provided key` | 2026-05-06 |
| Negativtest _hacked (first, Key A) | ❌ Datei ungültig | ❌ `Invalid datafile. Data size should be non-zero & a multiple of 4096` | 2026-05-06 |
| Negativtest _hacked (second, Key B) | ❌ Datei ungültig | ❌ `Invalid datafile. Data size should be non-zero & a multiple of 4096` | 2026-05-06 |
| Negativtest _bytechange (first, Key A) | ❌ Digest mismatch | ❌ `Signature block image digest does not match the actual image digest` | 2026-05-06 |
| Negativtest _bytechange (second, Key B) | ❌ Digest mismatch | ❌ `Signature block image digest does not match the actual image digest` | 2026-05-06 |

---

## Wichtige Hinweise

- **Keine eFuses setzen** während der Testphase (`espefuse.py burn_efuse ...` nicht ausführen).
- **Wegwerfschlüssel** in den Testordnern nicht in der Produktion verwenden.
- **Für die Produktion:** eFuses und Secure Boot erst aktivieren, nachdem OTA, Signaturprüfung und Rollback vollständig validiert sind.

# Recherche zu Rollback und Arduino OTA (theoretisch, nicht getestet)

[OTA Dokumentation Espressif](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/ota.html)

Dieses Wissen ist relevant für unser Provisioning-Projekt: Ein ESP-IDF-Projekt
mit Secure Boot und Full Flash Encryption wird zuerst geflasht. Anschließend
wird per OTA reiner Arduino-Code als neue Firmware geladen.

---

## Bedingungen für Rollback

1. **Bootloader-Konfiguration im Provisioning-Projekt:**
   `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y`
   Diese Option wird beim Kompilieren des Bootloaders eingebrannt und kann
   nachträglich (z.B. aus der Arduino-Firmware) **nicht** geändert werden.

2. **Partitionstabelle muss enthalten:**
   - `otadata` (Typ `data`, SubTyp `ota`)
   - Mindestens zwei App-Slots (`ota_0` / `ota_1` bzw. `app0` / `app1`)

3. **Validierungsaufruf in der Arduino-Firmware:**
   Nach erfolgreichem Boot muss `esp_ota_mark_app_valid_cancel_rollback()`
   aufgerufen werden – sonst rollt jede neue Firmware beim nächsten Reboot zurück.
   Nötiger Include: `#include "esp_ota_ops.h"`

---

## Ablauf bei OTA-Update

### Schreibphase (Arduino OTA)

```
Update.begin()          → esp_ota_begin()
Update.write()          → esp_ota_write()           [n-mal]
Update.end()            → esp_ota_end()
                          esp_ota_set_boot_partition()
                          → otadata: seq+1, PENDING_VERIFY
ESP.restart()           → Reboot
```

### Bootphase – Fall A: Korrekt signierte, funktionierende Firmware

```
OTA abgeschlossen:
  esp_ota_set_boot_partition() → schreibt NEW in otadata

Bootloader liest otadata → NEW
  → Secure Boot Check OK → App startet
  → setup() läuft, esp_ota_mark_app_valid_cancel_rollback() wird aufgerufen
  → otadata: VALID → dauerhaft aktiv
```

### Bootphase – Fall B: Falsch signierte Firmware (oder Korruption im Image)

```
OTA abgeschlossen:
  esp_ota_set_boot_partition() → schreibt NEW in otadata

Boot 1:
  Bootloader liest NEW
  → schreibt sofort PENDING_VERIFY in otadata
  → Secure Boot Check FAIL → abort() → Reset

Boot 2:
  Bootloader liest PENDING_VERIFY
  → "bereits versucht, nie bestätigt" → schreibt ABORTED
  → wählt vorherigen Slot (app0)
  → Secure Boot Check OK → alte Firmware läuft wieder
```

### Bootphase – Fall C: Korrekt signierte, aber crashende Firmware

```
OTA abgeschlossen:
  esp_ota_set_boot_partition() → schreibt NEW in otadata

Boot 1:
  Bootloader liest NEW
  → schreibt sofort PENDING_VERIFY in otadata
  → Secure Boot Check OK → App startet
  → Crash/Watchdog/Panic vor esp_ota_mark_app_valid_cancel_rollback()
  → automatischer Reset

Boot 2:
  Bootloader liest PENDING_VERIFY
  → "bereits versucht, nie bestätigt" → schreibt ABORTED
  → wählt vorherigen Slot (app0)
  → Secure Boot Check OK → alte Firmware läuft wieder
```

---

## Mögliche Fallstricke

| Fallstrick | Wirkung | Lösung |
|---|---|---|
| `esp_ota_mark_app_valid_cancel_rollback()` wird nie aufgerufen | Endlos-Rollback nach jedem OTA | Aufruf nach erfolgreicher Initialisierung in `setup()` |
| `esp_ota_mark_app_valid_cancel_rollback()` wird zu früh aufgerufen | Defekte Firmware wird als valide markiert | Erst nach kritischen Initialisierungen aufrufen (WiFi, Backend-Verbindung) |
| Bootloader ohne `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y` geflasht | Mechanismus inaktiv, keine Rollback-Reaktion | Bootloader aus Provisioning-Projekt mit korrekter sdkconfig neu kompilieren |
| Bootloader von Arduino-/pioarduino-Default überschrieben; (In Produktion unmöglich, aber wichtig zu beachten während development) | Eigene Provisioning-Konfiguration verloren | OTA darf nur App-Slots schreiben, niemals Bootloader |
| Nur ein App-Slot in Partitionstabelle | Kein Rollback-Ziel vorhanden | Partitionstabelle mit `ota_0`, `ota_1`, `otadata` |
| Crash vor `esp_ota_mark_app_valid_cancel_rollback()` durch Watchdog | Beabsichtigt → führt zu Rollback | Korrektes Verhalten, nichts zu tun |

---

## Wichtige Befehle

| Befehl | Framework | Nutzen | Anmerkung |
|---|---|---|---|
| `Update.begin/write/end()` | Arduino | OTA-Schreibvorgang | Wrapper für `esp_ota_*` |
| `esp_ota_set_boot_partition()` | ESP-IDF | Setzt neuen Slot auf `PENDING_VERIFY` | Wird intern von `Update.end()` aufgerufen |
| `esp_ota_mark_app_valid_cancel_rollback()` | ESP-IDF | Bestätigt Boot → State `VALID` | **Muss manuell aufgerufen werden** |
| `esp_ota_mark_app_invalid_rollback_and_reboot()` | ESP-IDF | Erzwingt sofortigen Rollback | Z.B. wenn App selbst Defekt erkennt |
| `esp_ota_get_state_partition()` | ESP-IDF | Liest aktuellen State eines Slots | Debug / Statusprüfung |
| `esp_ota_get_running_partition()` | ESP-IDF | Liefert aktuell laufende Partition | Für Statusabfragen |

---

## Beispiel-Code für Arduino-Firmware

```cpp
#include "esp_ota_ops.h"

void setup() {
    // sobald klar ist, dass App Stabil läuft
    esp_ota_mark_app_valid_cancel_rollback();
    // Restlicher code
}
```
