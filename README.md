# 📱 iOS Forensic Acquisition Tool v1.0

**Mobile Forensic Acquisition Suite - iOS Edition**  
Per **Tsurugi Linux 2026** e **macOS**

---

## Funzionalità

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
| **Hash Verification** | MD5 / SHA-1 / SHA-256 di tutti gli artefatti | Python `hashlib` |
| **Report Forense** | Report HTML + TXT con chain of custody | Generatore interno |

---

## Requisiti

### Python
- Python **3.7+** (incluso in Tsurugi e macOS)
- Moduli: solo libreria standard (`tkinter`, `hashlib`, `subprocess`, ecc.)

### Dipendenze di sistema

#### Tsurugi Linux 2026
```bash
# libimobiledevice (spesso già presente su Tsurugi)
sudo apt update
sudo apt install -y libimobiledevice-utils ideviceinstaller usbmuxd

# Per screen recording → video
sudo apt install -y ffmpeg

# Avvia usbmuxd (se non attivo)
sudo systemctl start usbmuxd
sudo systemctl enable usbmuxd
```

#### macOS
```bash
# Con Homebrew
brew install libimobiledevice ideviceinstaller

# Per screen recording → video
brew install ffmpeg

# usbmuxd è incluso in macOS nativamente
```

---

## Installazione

```bash
# Clona o copia il tool
git clone <repo-url> ios_forensic_tool
cd ios_forensic_tool

# Rendi eseguibile
chmod +x ios_forensic_acquisition.py

# Avvia
python3 ios_forensic_acquisition.py
# oppure
./ios_forensic_acquisition.py
```

---

## Guida Rapida

### 1. Prepara il Dispositivo iOS
1. Connetti l'iPhone/iPad via **cavo USB**
2. **Sblocca** il dispositivo
3. Se richiesto, tocca **"Autorizza"** / **"Trust This Computer"**

### 2. Avvia il Tool
```bash
python3 ios_forensic_acquisition.py
```

### 3. Workflow Forense Consigliato

1. **Tab Caso** → Inserisci numero caso, esaminatore, e clicca "Inizializza Caso"
2. **Rileva Dispositivo** → Bottone nella barra superiore
3. **Pair** → Se necessario, effettua pairing
4. **Tab Dispositivo** → Acquisisci e salva info dispositivo
5. **Tab App Installate** → Registra le app e salva la lista
6. **Tab Backup** → Avvia acquisizione backup (cifrato se possibile)
7. **Tab Screenshot** → Cattura screenshot o avvia screen recording
8. **Tab SysLog/Crash** → Cattura log di sistema e crash reports
9. **Tab Report** → Genera report forense HTML + TXT

### 4. Output
Tutti i dati vengono salvati in:
```
~/iOS_Forensic_Acquisitions/
└── Case_<NUMERO>_<TIMESTAMP>/
    ├── backup/                # Backup iTunes
    ├── device_info/           # Info dispositivo (TXT + JSON)
    ├── screenshots/           # Screenshot singoli
    ├── screen_recording/      # Frame + Video
    │   └── frames/
    ├── syslog/                # Log di sistema
    ├── crash_reports/         # Crash reports
    ├── app_list/              # Lista applicazioni
    ├── diagnostics/           # Info diagnostiche
    ├── reports/               # Report forensi HTML/TXT
    └── hashes/                # Hash di verifica
```

---

## Note Forensi

### Integrità dei Dati
- Ogni artefatto acquisito viene automaticamente hashato (MD5, SHA-1, SHA-256)
- I valori hash vengono registrati nel log e nel report finale
- Il backup viene verificato file per file con SHA-256

### Backup Cifrato
- iOS richiede la password del backup cifrato impostata sul dispositivo
- Il backup cifrato contiene **più dati** rispetto a quello non cifrato (keychain, password WiFi, health data, ecc.)
- Per acquisizioni forensi, il backup cifrato è **fortemente consigliato**

### Limitazioni iOS
- A differenza di Android/ADB, iOS **non espone la lista processi** senza jailbreak
- Le informazioni disponibili dipendono dal livello di trust e dalla versione iOS
- Il dispositivo **deve essere sbloccato** e deve aver autorizzato il computer

### Screen Recording
- Implementato come cattura screenshot sequenziale (non screen mirroring nativo)
- Il video viene generato con `ffmpeg` dai frame catturati
- Intervallo minimo consigliato: 0.5 secondi

---

## Troubleshooting

| Problema | Soluzione |
|---|---|
| "Nessun dispositivo rilevato" | Verifica cavo USB, sblocca iPhone, tocca "Autorizza" |
| "idevice_id non trovato" | Installa `libimobiledevice-utils` |
| Errore pairing | Rimuovi pairing: `idevicepair unpair`, poi riprova |
| Backup lento/fallito | Verifica spazio disco, prova senza cifratura |
| Screenshot fallito | Il dispositivo deve essere sbloccato e su schermata visibile |
| usbmuxd non attivo | `sudo systemctl start usbmuxd` (Linux) |

---

## Licenza

GPLv3 - Software libero per uso forense e investigativo.

---

*Tool sviluppato per integrazione con **Tsurugi Linux 2026** Digital Forensics Distribution.*
