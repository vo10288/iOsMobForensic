# Changelog

Il formato segue [Keep a Changelog](https://keepachangelog.com/it/1.1.0/)
e il progetto adotta il [Semantic Versioning](https://semver.org/lang/it/).

## [1.0.0] - non ancora rilasciata

### Corretto

Rilievi con impatto forense, descritti in dettaglio in `ANALISI.md`:

- **I crash report venivano rimossi dal dispositivo.** `idevicecrashreport`
  era invocato senza `--keep`, quindi spostava i report anziché copiarli,
  alterando il reperto in modo irreversibile.
- **Un file illeggibile risultava integro.** In caso di errore di lettura il
  digest veniva sostituito dal testo dell'eccezione; lo stesso errore si
  ripresentava in verifica, e il confronto passava.
- **Il manifest non sopravviveva allo spostamento del caso.** Conteneva il
  percorso assoluto della cartella, usato in verifica: copiare il caso su un
  supporto di conservazione rendeva impossibile la verifica.
- **La password del backup compariva in `ps`.** Era passata come argomento a
  `idevicebackup2 encryption on`, quindi leggibile da ogni utente del sistema.
  Ora transita su stdin.
- **L'estrazione media dal backup non trovava quasi nulla.** Il filtro era per
  estensione, ma i file di un backup iOS hanno nomi opachi e nessuna
  estensione. Il tipo è ora dedotto dalle firme dei byte iniziali.
- **Doppio conteggio nel parser syslog.** Due espressioni regolari applicate
  alla stessa riga contavano due volte ogni processo con sottosistema.
- **Un frame perso troncava il video.** La numerazione con buchi fermava il
  demuxer `image2` di ffmpeg al primo indice mancante.
- **`-u UDID` posizionato dopo il sottocomando** in `idevicediagnostics`,
  dove `getopt` lo ignora: con più dispositivi collegati agiva su quello
  sbagliato.
- **Stallo potenziale durante il backup**, per lettura sequenziale di stdout e
  stderr su due pipe distinte.
- **Il manifest includeva sé stesso**, rendendo sempre difforme la verifica
  successiva alla seconda generazione.
- **Licenza incoerente**: il README dichiarava GPLv3 mentre `LICENSE`
  conteneva CC0-1.0. Il progetto adotta ora `GPL-3.0-or-later`.
- `ideviceinstaller -o list_user`, sintassi legacy che fallisce sulle versioni
  recenti: ora con fallback su `list --user`.
- `except:` nudo in `get_platform_info()`, che catturava anche
  `KeyboardInterrupt`.

### Aggiunto
- Interfaccia a riga di comando `iosforensic` con sottocomandi `doctor`,
  `devices`, `init`, `info`, `apps`, `backup`, `syslog`, `crash`,
  `provisioning`, `afc`, `analyze`, `hash`, `verify`, `report` e `gui`.
- Comando `doctor` per la verifica preventiva delle dipendenze esterne.
- Audit log append-only per caso (`audit.log`), sincronizzato su disco a ogni
  voce: una interruzione a metà acquisizione non perde più la tracciabilità.
- Metadati del caso persistiti in `case.json`.
- Confronto fra l'orologio del dispositivo e quello della workstation, incluso
  nel riepilogo: uno scostamento cambia l'interpretazione di ogni timestamp.
- Rilevamento della cifratura del backup da `Manifest.plist`.
- Rilevamento dei marker di backup (`Manifest.db`, `Info.plist`, `Status.plist`).
- 21 test automatici, con casi di regressione per i bug elencati sopra.
- Workflow di CI su GitHub Actions (Linux e macOS, Python 3.9 / 3.11 / 3.13).
- `THIRD_PARTY_NOTICES.md` con le licenze delle dipendenze esterne.
- `ANALISI.md` con i rilievi sul codice precedente.

### Modificato
- Il codice è organizzato nel package `iosforensic`, con logica di dominio,
  GUI e CLI separate.
- L'inserimento di `-u <UDID>` è centralizzato in `DeviceInterface.run()` e
  avviene sempre prima del sottocomando.
- La copia AFC preserva la struttura di cartelle del dispositivo: il percorso
  originale di un file è esso stesso un dato.
- Il report distingue esplicitamente i limiti dell'acquisizione logica e
  presenta l'analisi dei processi come ricostruzione indiziaria.

### Rimosso
- Le copie duplicate `ios_forensic_acquisition-2/-3/-4.py`. Restano
  accessibili nello storico e sotto il tag `v0.9-pre-refactor`.
- L'archivio `files (15).zip` dal versionamento.
