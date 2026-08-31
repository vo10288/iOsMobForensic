# Contribuire

Grazie per l'interesse. Poche regole, tutte con una ragione pratica.

## Licenza dei contributi

Inviando una pull request accetti che il tuo contributo sia distribuito sotto
**GPL-3.0-or-later**, la stessa licenza del progetto. Non è richiesto firmare
un CLA. Ogni nuovo file sorgente deve iniziare con:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) <anno>  <autore>
```

## Ambito

Sono benvenuti: nuovi artefatti acquisibili tramite canali ufficiali, parser,
miglioramenti al report, test, traduzioni.

Sono **fuori ambito** e verranno rifiutati: exploit, bypass del codice di
sblocco, aggiramento della Data Protection, tecniche basate su jailbreak.
Questo progetto resta uno strumento di acquisizione logica su dispositivi ai
quali si ha accesso legittimo.

## Prima di aprire una PR

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -q
python3 -m ruff check .
```

## Requisiti per il codice

- Python 3.9+, solo libreria standard nel package `iosforensic`. Dipendenze
  esterne solo come strumenti invocati via `subprocess`: è ciò che tiene
  separate le licenze e semplifica il deployment su Tsurugi.
- Type hint sulle firme pubbliche, docstring in italiano.
- Nessun `subprocess.run` con `shell=True`.
- Le operazioni che leggono o scrivono nel caso passano da `Case.log()`:
  un'operazione non tracciata è un buco nella catena di custodia.
- Ogni funzione che tocca hash, manifest o verifica di integrità deve avere
  un test. Quella parte regge il valore probatorio degli artefatti.

## Segnalare vulnerabilità

Non aprire una issue pubblica. Usa la scheda Security del repository, tramite
la funzione di private vulnerability reporting.
