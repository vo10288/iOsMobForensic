# Analisi del codice originale

Rilievi emersi leggendo `ios_forensic_acquisition.py` (3184 righe). Ordinati
per impatto forense, non per gravità tecnica: un bug che produce un report
sbagliato conta più di uno che fa crashare il programma, perché il secondo si
nota subito e il primo no.

---

## Critici: alterano il reperto o falsano la verifica

### 1. I crash report vengono cancellati dal dispositivo

`extract_crash_reports()`, riga 500:

```python
cmd.extend(["-e", output_dir])  # -e = extract
```

Manca `--keep`. Senza quel flag `idevicecrashreport` **sposta** i report: li
copia sulla workstation e li rimuove dal dispositivo. Il reperto viene alterato
in modo irreversibile, e un consulente di controparte che ripetesse
l'acquisizione non troverebbe più nulla.

È il rilievo più serio dei tre. Nel nuovo `device.py` il valore predefinito è
`keep_on_device=True`, e la rimozione richiede un `--purge` esplicito che
registra un avviso nell'audit log.

### 2. Un file illeggibile risulta "integro"

`calculate_hash()`, righe 139-141:

```python
except Exception as e:
    for algo in algorithms:
        hashes[algo] = f"ERRORE: {e}"
```

Il digest viene sostituito dal testo dell'errore. In fase di verifica lo stesso
file produce lo stesso errore, quindi le due stringhe coincidono e
`verify_hash_manifest()` lo marca `OK`. Un file corrotto o non leggibile passa
la verifica di integrità.

Ora l'eccezione si propaga e l'operatore la vede. Coperto da
`test_unreadable_file_does_not_produce_fake_hash`.

### 3. Il manifest non sopravvive allo spostamento del caso

`create_hash_manifest()` salva il percorso assoluto:

```python
json.dump({"directory": directory, ...})
```

e `verify_hash_manifest()` lo riusa:

```python
base_dir = manifest.get("directory", "")
fpath = os.path.join(base_dir, entry["file"])
```

Copiare il caso su un disco di conservazione — cosa che si fa sempre — rende la
verifica impossibile: cerca i file nel percorso originale, che non esiste più.
Il manifest ora usa percorsi relativi alla radice del caso. Coperto da
`test_manifest_paths_are_relative_and_portable`.

### 4. La password del backup finisce in `ps`

`start_backup()`, riga 404:

```python
enc_cmd.extend(["encryption", "on", password])
```

La riga di comando di un processo è leggibile da qualunque utente del sistema.
Su una workstation condivisa, o con un utente non privilegiato attivo, la
password del backup cifrato è esposta per tutta la durata del comando. Ora
viene passata su stdin.

---

## Funzionali: la funzione non fa quello che dice

### 5. L'estrazione media dal backup non trova quasi nulla

`find_media_in_backup()` filtra per estensione:

```python
_, ext = os.path.splitext(fname.lower())
if ext in target_exts:
```

In un backup iOS i file sono nominati con lo SHA-1 del percorso originale e
**non hanno estensione**. Un file come `a3f1b2c4...` è una foto, ma
`os.path.splitext` restituisce stringa vuota, quindi il filtro lo scarta. Su un
backup reale la funzione restituisce quasi zero risultati.

Il nuovo `backup.py` deduce il tipo dai byte iniziali (firme JPEG, PNG, HEIC,
MOV, SQLite, bplist e altre), che è l'unico modo che funzioni su un backup non
cifrato.

### 6. Doppio conteggio nel parser syslog

`parse_syslog_file()` applica due espressioni regolari alla stessa riga:

```python
match = PROCESS_PATTERN.search(line)     # incrementa count
match2 = SUBSYSTEM_PATTERN.search(line)  # incrementa di nuovo
```

Una riga nel formato `SpringBoard(FrontBoard)[62]` corrisponde a entrambe, e le
occorrenze del processo vengono contate due volte. Il report dei processi
riporta numeri gonfiati, in misura variabile a seconda di quanti processi
usano un sottosistema.

Ora un solo pattern con gruppo opzionale. Coperto da
`test_subsystem_lines_are_not_counted_twice`.

### 7. Un frame perso tronca l'intero video

`_record_loop()` incrementa `frame_count` prima della cattura e, in caso di
errore, prosegue senza produrre il file. Si crea un buco nella numerazione:
`frame_000001.png`, `frame_000003.png`. Poi:

```python
pattern = os.path.join(self.output_dir, "frame_%06d.png")
cmd = ["ffmpeg", "-y", "-framerate", str(fps), "-i", pattern, ...]
```

Il demuxer `image2` di ffmpeg si ferma al primo indice mancante. Un singolo
screenshot fallito — cosa ordinaria su USB — tronca il video a quel punto,
silenziosamente.

Il nuovo `recorder.py` incrementa solo dopo una cattura riuscita e usa il
demuxer `concat` con elenco esplicito dei frame, immune ai buchi.

### 8. `-u UDID` posizionato dopo il sottocomando

`get_diagnostics()`, righe 528-530:

```python
cmd = ["idevicediagnostics", "diagnostics", diag_type]
if self.udid:
    cmd.extend(["-u", self.udid])
```

Risultato: `idevicediagnostics diagnostics All -u <UDID>`. Le utility
libimobiledevice analizzano le opzioni con `getopt`, che si ferma al primo
argomento posizionale: `-u` viene ignorato. Con un solo dispositivo collegato
funziona per caso; con due, il comando agisce sul dispositivo sbagliato.

Ora l'inserimento dell'UDID è centralizzato in `DeviceInterface.run()` e
avviene sempre subito dopo il nome del programma.

### 9. Deadlock potenziale durante il backup

`start_backup()` legge `process.stdout` in un ciclo e solo dopo:

```python
stderr = process.stderr.read()
```

Se `idevicebackup2` scrive su stderr più di quanto entri nel buffer della pipe
(64 KB su Linux), il processo figlio si blocca in scrittura mentre il padre
attende su stdout. Stallo permanente, a metà di un backup. Ora i due flussi
sono uniti con `stderr=subprocess.STDOUT`.

### 10. `unmount_afc` su Linux presuppone `fusermount` nel PATH

Corretto come logica (`fusermount -u` su Linux, `umount` su macOS), ma
l'errore non veniva distinto da un mount inesistente. Marginale, segnalato per
completezza.

---

## Strutturali

### 11. `ideviceinstaller -o list_user` è sintassi legacy

Le versioni recenti hanno sostituito `-l -o list_user` con `list --user`. Sui
sistemi aggiornati, incluso Tsurugi 2026, il comando originale fallisce. Il
nuovo codice prova la sintassi legacy e ricade su quella nuova.

### 12. `except:` nudo

Riga 203, in `get_platform_info()`. Cattura anche `KeyboardInterrupt` e
`SystemExit`. Sostituito con `except OSError`.

### 13. Nessun audit log persistente

`acquisition_log` è una lista in memoria, riversata nel report solo alla fine.
Se il programma va in crash a metà acquisizione — o se la workstation si spegne
— la tracciabilità di quanto già fatto è perduta. Ora ogni operazione è scritta
in `audit.log` con `fsync` immediato.

### 14. Il manifest include sé stesso

`create_hash_manifest()` percorre l'intera directory del caso, inclusa la
cartella `hashes/`. Rieseguendolo, il manifest precedente entra nel nuovo,
e la seconda verifica segnala sempre una difformità. Ora `hashes/` e
`audit.log` sono esclusi per costruzione.

---

## Cosa era già fatto bene

Vale la pena dirlo, perché il refactor ha conservato queste scelte:

- L'inizializzazione di `acquisition_log` e `_artifacts_list` **prima** di
  `iOSDeviceInterface`, con il commento che ne spiega il motivo (riga 1414).
  È esattamente il tipo di trappola che si scopre una volta sola.
- L'uso di `_run_in_thread` per non bloccare la GUI: l'impianto c'era già.
- Il calcolo di più digest in un'unica lettura del file.
- Il fallback della lista app su formati di output alternativi.
- La separazione fra `find_media_in_backup` e `extract_media_from_backup`,
  che rende la ricerca testabile indipendentemente dalla copia.
