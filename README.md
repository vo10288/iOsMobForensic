# 📱 iOS Forensic Acquisition Tool v1.0

**Mobile Forensic Acquisition Suite - iOS Edition**  
Per **Tsurugi Linux 2026** e **macOS**

---

## Funzionalità

### Acquisizione Dati

| Funzione | Descrizione | Tool Backend |
|---|---|---|
| **Backup Completo** | Acquisizione backup iTunes-style (cifrato/non cifrato) | `idevicebackup2` |
| **Info Dispositivo** | UDID, modello, iOS version, seriale, batteria, disco | `ideviceinfo` |
| **Lista App** | App utente, sistema o tutte con bundle ID | `ideviceinstaller` |
| **Screenshot** | Cattura singola dello schermo | `idevicescreenshot` |
| **Screen Recording** | Registrazione tramite screenshot sequenziali + video | `idevicescreenshot` + `ffmpeg` |
| **System Log** | Cattura syslog con durata e filtro configurabili | `idevicesyslog` |
| **Crash Reports** | Estrazione crash reports dal dispositivo | `idevicecrashreport` |
| **Diagnostica** | Info diagnostiche hardware/software | `idevicediagnostics` |

### File & Media

| Funzione | Descrizione | Tool Backend |
|---|---|---|
| **Accesso AFC** | Mount/scan/copia file via Apple File Conduit | `ifuse` |
| **Estrazione Media** | Copia automatica immagini, video, audio, documenti | `ifuse` + Python |
| **Analisi Backup** | Statistiche: tipo file, dimensioni, struttura | Python |
| **Media dal Backup** | Estrazione e categorizzazione media dal backup | Python |
| **Provisioning Profiles** | Estrazione profili di provisioning | `ideviceprovision` |
| **Info Attivazione** | Stato attivazione del dispositivo | `ideviceactivation` |

### Analisi & Integrità

| Funzione | Descrizione | Tool Backend |
|---|---|---|
| **Analisi Processi** | Estrazione processi attivi dal syslog | Python (regex parser) |
| **Hash Manifest** | Creazione manifest MD5/SHA-1/SHA-256 dell'intero caso | Python `hashlib` |
| **Verifica Integrità** | Confronto hash per rilevare file alterati/mancanti | Python |
| **Report Forense** | Report HTML + TXT con chain of custody | Generatore interno |

---

## Architettura

```
ios_forensic_acquisition.py (3180+ righe, 7 classi, 51+ metodi GUI)
│
├── iOSDeviceInterface        → Comunicazione con dispositivo (22 metodi)
├── SyslogProcessParser        → Analisi processi da syslog
├── BackupAnalyzer             → Statistiche e media extraction dal backup
├── IntegrityVerifier          → Hash manifest + verifica integrità
├── ScreenRecorder             → Recording via screenshot sequenziali + ffmpeg
├── ForensicReportGenerator    → Report HTML + TXT
│
└── iOSForensicApp (GUI)       → 9 tab tkinter
    ├── 📋 Caso                → Info caso ed esaminatore
    ├── 📱 Dispositivo         → Info dispositivo complete
    ├── 💾 Backup              → Acquisizione backup
    ├── 📸 Screenshot          → Cattura + registrazione
    ├── 📋 SysLog/Crash        → Log sistema + crash reports
    ├── 📦 App Installate      → Lista app con salvataggio
    ├── 📂 File & Media        → AFC + analisi backup + provisioning
    ├── 🔒 Integrità           → Hash manifest + verifica + processi
    └── 📄 Report              → Generazione report forense
```

---

## Requisiti

### Python
- Python **3.7+** (incluso in Tsurugi e macOS)
- Moduli: solo libreria standard (`tkinter`, `hashlib`, `subprocess`, ecc.)

### Dipendenze di sistema

#### Tsurugi Linux 2026
```bash
sudo apt update
sudo apt install -y libimobiledevice-utils ideviceinstaller usbmuxd
sudo apt install -y ifuse       # Per accesso file AFC
sudo apt install -y ffmpeg      # Per screen recording → video
sudo systemctl start usbmuxd
sudo systemctl enable usbmuxd
```

#### macOS
```bash
brew install libimobiledevice ideviceinstaller
brew install ifuse              # Per accesso file AFC
brew install --cask macfuse     # Richiesto da ifuse su macOS
brew install ffmpeg             # Per screen recording → video
```

---

## Installazione e Avvio

```bash
mkdir ~/IosForensicAcquisition
cp ios_forensic_acquisition.py launch.sh ~/IosForensicAcquisition/
cd ~/IosForensicAcquisition
chmod +x launch.sh ios_forensic_acquisition.py

# Avvia (con check dipendenze)
bash launch.sh

# Oppure direttamente
python3 ios_forensic_acquisition.py
```

---

## Workflow Forense Consigliato

1. **📋 Caso** → Inserisci numero caso, esaminatore → "Inizializza Caso"
2. **Barra superiore** → "Rileva Dispositivo" → "Pair" (se necessario)
3. **📱 Dispositivo** → Acquisisci e salva info dispositivo
4. **📦 App Installate** → Registra le app e salva la lista
5. **💾 Backup** → Avvia acquisizione backup (cifrato se possibile)
6. **📸 Screenshot** → Cattura screenshot / avvia screen recording
7. **📋 SysLog/Crash** → Cattura log di sistema e crash reports
8. **📂 File & Media** → Monta AFC, scansiona, copia media
9. **📂 File & Media** → Analizza backup ed estrai media
10. **🔒 Integrità** → Crea hash manifest dell'intero caso
11. **🔒 Integrità** → Analizza processi dal syslog
12. **📄 Report** → Genera report forense HTML + TXT

### Struttura Output
```
~/iOS_Forensic_Acquisitions/
└── Case_<NUMERO>_<TIMESTAMP>/
    ├── backup/                   # Backup iTunes
    ├── backup_media/             # Media estratti dal backup
    ├── device_info/              # Info dispositivo (TXT + JSON)
    ├── screenshots/              # Screenshot singoli
    ├── screen_recording/frames/  # Frame + Video
    ├── syslog/                   # Log sistema + report processi
    ├── crash_reports/            # Crash reports
    ├── app_list/                 # Lista applicazioni
    ├── diagnostics/              # Info diagnostiche
    ├── provisioning_profiles/    # Profili provisioning
    ├── afc_media/                # Media copiati via AFC
    ├── reports/                  # Report forensi HTML/TXT + analisi
    └── hashes/                   # Hash manifest (TXT + JSON)
```

---

## Note Forensi

- Ogni artefatto viene hashato MD5 / SHA-1 / SHA-256 automaticamente
- Il manifest può essere verificato in qualsiasi momento per rilevare alterazioni
- Il backup cifrato contiene più dati (keychain, health, WiFi passwords) ed è raccomandato
- L'analisi processi dal syslog compensa l'impossibilità di accedere a `ps` senza jailbreak
- AFC richiede `ifuse` e su macOS anche `macFUSE`

---

## Troubleshooting

| Problema | Soluzione |
|---|---|
| Nessun dispositivo rilevato | Verifica cavo USB, sblocca iPhone, tocca "Autorizza" |
| idevice_id non trovato | `apt install libimobiledevice-utils` |
| Errore pairing | `idevicepair unpair`, poi riprova |
| Backup fallito | Verifica spazio disco, prova senza cifratura |
| AFC mount fallito | Installa `ifuse` + `macFUSE` (macOS) |
| usbmuxd non attivo | `sudo systemctl start usbmuxd` (Linux) |
| Pochi processi da syslog | Cattura syslog più lungo (60-120 sec) |

---

## Licenza

Creative Commons CC0 1.0 Universal - Software libero per uso forense e investigativo.

*Tool sviluppato per integrazione con **Tsurugi Linux 2026** Digital Forensics Distribution.*
