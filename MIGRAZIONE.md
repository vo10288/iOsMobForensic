# Guida alla migrazione

Procedura per portare il repository dalla struttura attuale (quattro script
duplicati alla radice) a questa, senza perdere nulla dello storico.

## 1. Metti al sicuro lo stato attuale

Prima di ogni cosa, assicurati che tutto il lavoro esistente sia committato su
`main`. Anche i file che intendi eliminare: se sono in git, resteranno
recuperabili per sempre.

```bash
git clone https://github.com/vo10288/iOsMobForensic.git
cd iOsMobForensic
git status                    # non deve restare nulla di non tracciato
git add -A && git commit -m "Snapshot dello stato pre-refactor"
git push origin main
git tag -a v0.9-pre-refactor -m "Ultimo stato prima della riorganizzazione"
git push origin v0.9-pre-refactor
```

Il tag è la rete di sicurezza: qualunque cosa succeda dopo, `git checkout
v0.9-pre-refactor` riporta esattamente allo stato di partenza.

## 2. Crea il branch di lavoro

```bash
git checkout -b refactor/struttura-e-licenza
```

## 3. Applica i file nuovi

Copia il contenuto di questa consegna nella radice del repository, poi:

```bash
git rm --cached "files (15).zip"          # esce dal repo, resta su disco
git rm ios_forensic_acquisition-2.py \
       ios_forensic_acquisition-3.py \
       ios_forensic_acquisition-4.py
```

I tre file eliminati non spariscono: restano nello storico e sotto il tag
`v0.9-pre-refactor`. È esattamente il motivo per cui esiste git.

Per `ios_forensic_acquisition.py` (il file principale) vedi il punto 5.

## 4. Commit separati

Non un unico commit da 40 file. Separali per intento, così il diff resta
leggibile e ogni cambiamento è annullabile da solo:

```bash
git add LICENSE THIRD_PARTY_NOTICES.md
git commit -m "Adotta GPL-3.0-or-later, risolvendo il conflitto con CC0

Il README dichiarava GPLv3 mentre il file LICENSE conteneva CC0-1.0.
Si adotta la GPL-3.0-or-later, coerente con l'intento del README.
Aggiunge THIRD_PARTY_NOTICES.md con le licenze delle dipendenze esterne."

git add pyproject.toml .gitignore
git commit -m "Aggiunge packaging con setuptools ed entry point iosforensic"

git add iosforensic/
git commit -m "Riorganizza il codice in package: core, GUI e CLI separati"

git add tests/ .github/
git commit -m "Aggiunge test su integrità e parser, più CI su GitHub Actions"

git add README.md CONTRIBUTING.md CHANGELOG.md MIGRAZIONE.md ANALISI.md
git commit -m "Riscrive la documentazione e documenta i rilievi sul codice

ANALISI.md raccoglie i problemi emersi durante il refactor, fra cui la
rimozione dei crash report dal dispositivo e la verifica di integrità che
passava su file illeggibili."

git rm ios_forensic_acquisition-*.py
git commit -m "Rimuove le copie duplicate dello script

Le versioni -2, -3 e -4 restano accessibili nello storico e sotto il tag
v0.9-pre-refactor. Il versionamento è ora affidato a git."
```

## 5. Corrispondenza con il codice originale

I moduli in `iosforensic/` sono il refactor di `ios_forensic_acquisition.py`:
tutte le 22 funzioni di `iOSDeviceInterface` sono state portate, AFC inclusa.
I rilievi emersi durante il lavoro sono in `ANALISI.md`.

| Classe originale | Modulo di destinazione |
| --- | --- |
| `iOSDeviceInterface` | `iosforensic/device.py` → `DeviceInterface` |
| `SyslogProcessParser` | `iosforensic/parsers.py` |
| `BackupAnalyzer` | `iosforensic/backup.py` |
| `IntegrityVerifier` | `iosforensic/integrity.py` |
| `ScreenRecorder` | `iosforensic/recorder.py` |
| `ForensicReportGenerator` | `iosforensic/report.py` |
| `iOSForensicApp` | `iosforensic/gui/app.py` → `ForensicApp` |

Restano da verificare sul campo, perché dipendono dall'hardware e non sono
coperte dai test automatici:

- il mount AFC con `ifuse`, sia generale sia con `--documents <bundle_id>`;
- il fallback di `ideviceinstaller` fra sintassi legacy e nuova, che dipende
  dalla versione installata sulla tua distribuzione;
- la cifratura del backup via stdin: verifica che la tua versione di
  `idevicebackup2` accetti la password sul flusso di input anziché come
  argomento, e in caso contrario segnalalo;
- il layout dei nuovi tab della GUI a diverse risoluzioni.

Conserva il vecchio file finché non hai completato queste verifiche:

```bash
git mv ios_forensic_acquisition.py legacy/monolith_v0.9.py
```

Quando ogni funzionalità è stata provata su un dispositivo reale, eliminalo con
un commit dedicato. Fino ad allora resta il riferimento per il confronto.

## 6. Verifica prima di pubblicare

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -q
python3 -m ruff check .
iosforensic doctor
```

Poi una prova completa su un dispositivo di test — mai su un reperto reale:

```bash
iosforensic init --case TEST-001 --examiner "Nome Cognome" --root /tmp/test
iosforensic devices
iosforensic info --case-dir /tmp/test/Case_TEST-001_*
iosforensic hash --case-dir /tmp/test/Case_TEST-001_*
iosforensic verify --case-dir /tmp/test/Case_TEST-001_*
iosforensic report --case-dir /tmp/test/Case_TEST-001_*
```

## 7. Pubblica il branch

```bash
git push -u origin refactor/struttura-e-licenza
```

Apri poi una Pull Request verso `main` dall'interfaccia di GitHub. Anche
lavorando da solo conviene: la PR ti dà il diff completo prima del merge, e la
sua descrizione diventa la documentazione del *perché* di questi cambiamenti,
che fra sei mesi vale più del codice stesso.

Quando la unisci, usa "Squash and merge" solo se vuoi un singolo commit su
`main`; con i commit separati del punto 4, un merge normale conserva meglio la
storia.

## 8. Dopo il merge

```bash
git checkout main && git pull
git tag -a v1.0.0 -m "Prima release strutturata: package, CLI, GPL-3.0"
git push origin v1.0.0
```

Da GitHub, crea poi una Release a partire dal tag. Se vuoi distribuire
`files (15).zip` o altri asset binari, quello è il posto giusto: allegati alla
Release, non versionati nel repository.
