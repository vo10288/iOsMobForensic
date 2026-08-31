# iOS Forensic Acquisition Tool

**Suite di acquisizione forense logica per dispositivi iOS**
Per [Tsurugi Linux](https://tsurugi-linux.org) e macOS.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

---

## Cos'è

Un front-end Python (CLI + GUI tkinter) che orchestra la suite
[libimobiledevice](https://libimobiledevice.org) per eseguire **acquisizioni logiche**
di dispositivi iPhone e iPad, producendo un caso strutturato, hashato e
documentato da un report con chain of custody.

Non richiede jailbreak e non aggira alcuna protezione del dispositivo: opera
esclusivamente tramite i canali ufficiali `usbmuxd`/`lockdownd`, e richiede
quindi accesso fisico al dispositivo, sblocco e accettazione del pairing
("Autorizza questo computer") da parte di chi ne ha titolo.

## Ambito e limiti

| Supportato | Non supportato |
| --- | --- |
| Acquisizione logica (backup iTunes-style) | Acquisizione fisica / full file system |
| Backup cifrato (include keychain, Health, WiFi) | Bypass del codice di sblocco |
| Media via AFC, crash report, syslog | Estrazione da dispositivi bloccati |
| Provisioning profile, diagnostica, lista app | Acquisizione via jailbreak o exploit |

Il backup **cifrato** è raccomandato: contiene sensibilmente più artefatti del
backup in chiaro. La password del backup va registrata nel verbale.

---

## Funzionalità

### Acquisizione

| Funzione | Descrizione | Backend |
| --- | --- | --- |
| Backup completo | Backup iTunes-style, cifrato o in chiaro | `idevicebackup2` |
| Info dispositivo | UDID, modello, versione iOS, seriale, batteria, disco | `ideviceinfo` |
| Lista app | App utente, di sistema o tutte, con bundle ID | `ideviceinstaller` |
| Screenshot | Cattura singola dello schermo | `idevicescreenshot` |
| Screen recording | Screenshot sequenziali assemblati in video | `idevicescreenshot` + `ffmpeg` |
| System log | Cattura syslog con durata e filtro configurabili | `idevicesyslog` |
| Crash report | Estrazione dei crash report dal dispositivo | `idevicecrashreport` |
| Diagnostica | Informazioni diagnostiche hardware e software | `idevicediagnostics` |
| Provisioning profile | Estrazione dei profili di provisioning | `ideviceprovision` |

### File e media

| Funzione | Descrizione | Backend |
| --- | --- | --- |
| Accesso AFC | Mount, scansione e copia via Apple File Conduit | `ifuse` |
| Estrazione media | Copia di immagini, video, audio e documenti | `ifuse` + Python |
| Analisi backup | Statistiche su tipi di file, dimensioni e struttura | Python |
| Media dal backup | Estrazione e categorizzazione dei media dal backup | Python |

### Analisi e integrità

| Funzione | Descrizione | Backend |
| --- | --- | --- |
| Analisi processi | Ricostruzione dei processi attivi dal syslog | Python |
| Hash manifest | Manifest MD5 / SHA-1 / SHA-256 dell'intero caso | `hashlib` |
| Verifica integrità | Confronto hash per rilevare file alterati o mancanti | Python |
| Report forense | Report HTML e TXT con chain of custody | Python |

---

## Requisiti

- **Python 3.9+** (solo libreria standard, `tkinter` incluso per la GUI)
- **libimobiledevice** e utility correlate
- **ifuse** (opzionale, per l'accesso AFC)
- **ffmpeg** (opzionale, per lo screen recording)

### Tsurugi Linux / Debian / Ubuntu

```bash
sudo apt update
sudo apt install -y libimobiledevice-utils ideviceinstaller usbmuxd python3-tk
sudo apt install -y ifuse ffmpeg          # opzionali
sudo systemctl enable --now usbmuxd
```

### macOS

```bash
brew install libimobiledevice ideviceinstaller python-tk
brew install ifuse ffmpeg                 # opzionali
brew install --cask macfuse               # richiesto da ifuse
```

---

## Installazione

```bash
git clone https://github.com/vo10288/iOsMobForensic.git
cd iOsMobForensic
python3 -m pip install -e .
```

Oppure senza installare, direttamente dalla cartella del repository:

```bash
python3 -m iosforensic --help
```

## Uso

### Verifica dell'ambiente

Da eseguire sempre **prima** di collegare il dispositivo di interesse:

```bash
iosforensic doctor
```

Elenca i tool esterni presenti, quelli mancanti e le rispettive versioni.

### GUI

```bash
iosforensic gui
```

### CLI

```bash
# Rileva i dispositivi collegati
iosforensic devices

# Inizializza un caso
iosforensic init --case 2026-042 --examiner "M. Rossi" --notes "Sequestro del 12/03"

# Acquisisci le informazioni del dispositivo
iosforensic info --case-dir ~/iOS_Forensic_Acquisitions/Case_2026-042_20260312-101500

# Backup cifrato
iosforensic backup --case-dir <CASE_DIR> --encrypted

# Crash report, provisioning profile
iosforensic crash --case-dir <CASE_DIR>
iosforensic provisioning --case-dir <CASE_DIR>

# Mount AFC, scansione e copia dei media
iosforensic afc --case-dir <CASE_DIR> --copy --categories images,videos

# Manifest degli hash e verifica
iosforensic hash --case-dir <CASE_DIR>
iosforensic verify --case-dir <CASE_DIR>

# Report finale
iosforensic report --case-dir <CASE_DIR>
```

---

## Workflow consigliato

1. `iosforensic doctor` — verifica l'ambiente sulla workstation
2. Documenta lo stato del dispositivo (foto, batteria, notifiche, modalità aereo)
3. `init` — apri il caso con numero ed esaminatore
4. `devices` e pairing — `idevicepair pair`
5. `info` — informazioni complete del dispositivo
6. `apps` — inventario delle applicazioni installate
7. `backup --encrypted` — acquisizione principale
8. `syslog`, `crash`, `diagnostics` — artefatti volatili e di sistema
9. `afc` — media accessibili via Apple File Conduit
10. `analyze` — analisi del backup ed estrazione media
11. `hash` — manifest crittografico dell'intero caso
12. `report` — report HTML e TXT

### Struttura di output

```
~/iOS_Forensic_Acquisitions/
└── Case_<NUMERO>_<TIMESTAMP>/
    ├── case.json                 # Metadati del caso
    ├── audit.log                 # Log append-only di ogni operazione
    ├── backup/                   # Backup iTunes-style
    ├── backup_media/             # Media estratti dal backup
    ├── device_info/              # Info dispositivo (TXT + JSON)
    ├── screenshots/              # Screenshot singoli
    ├── screen_recording/         # Frame e video
    ├── syslog/                   # Log di sistema e analisi processi
    ├── crash_reports/            # Crash report
    ├── app_list/                 # Inventario applicazioni
    ├── diagnostics/              # Informazioni diagnostiche
    ├── provisioning_profiles/    # Profili di provisioning
    ├── afc_media/                # Media copiati via AFC
    ├── reports/                  # Report forensi HTML e TXT
    └── hashes/                   # Manifest degli hash (TXT + JSON)
```

---

## Note forensi

- Ogni artefatto viene hashato con MD5, SHA-1 e SHA-256 al momento
  dell'acquisizione; il manifest è riverificabile in qualsiasi momento.
- Ogni operazione è registrata in `audit.log` con timestamp UTC, comando
  eseguito, esito e durata.
- L'analisi dei processi dal syslog è una ricostruzione **indiziaria**: senza
  jailbreak non è possibile ottenere l'output di `ps`. Va presentata come tale.
- Il backup cifrato è preferibile a quello in chiaro. Se il dispositivo ha già
  una password di backup impostata e sconosciuta, va documentato.
- Lo strumento modifica lo stato del dispositivo nella misura minima
  necessaria (creazione del pairing record). Ciò va indicato nel verbale.

## Avvertenza legale

Questo software va utilizzato esclusivamente su dispositivi per i quali si
disponga di un titolo giuridico valido: proprietà, consenso informato
dell'avente diritto, incarico peritale o provvedimento dell'autorità
giudiziaria. L'uso non autorizzato può integrare reato (in Italia, tra gli
altri, artt. 615-ter e 617-quater c.p.). L'onere della verifica è
esclusivamente dell'utilizzatore.

---

## Analisi del codice precedente

I rilievi emersi durante la riorganizzazione — inclusi quattro problemi che
incidevano sull'integrità del reperto — sono documentati in
[ANALISI.md](ANALISI.md).

## Licenza

Distribuito nei termini della **GNU General Public License v3.0 o successiva**
(`GPL-3.0-or-later`). Il testo completo è in [LICENSE](LICENSE).

Questo programma è distribuito **senza alcuna garanzia**, neppure di
commerciabilità o idoneità a uno scopo particolare.

Le dipendenze esterne sono programmi separati, invocati come processi
indipendenti e non collegati a questo codice. Le loro licenze sono riepilogate
in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Contribuire

Vedi [CONTRIBUTING.md](CONTRIBUTING.md).
