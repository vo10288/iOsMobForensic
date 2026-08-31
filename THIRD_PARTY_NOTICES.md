# Third-Party Notices

`iOS Forensic Acquisition Tool` è rilasciato sotto **GPL-3.0-or-later**.

## Natura del rapporto con le dipendenze

Il codice di questo progetto **non incorpora, non collega staticamente e non
collega dinamicamente** alcuna libreria di terze parti. Utilizza esclusivamente
la libreria standard di Python.

Tutti gli strumenti elencati sotto vengono invocati come **processi separati**
tramite `subprocess`, scambiando dati attraverso argomenti da riga di comando,
stdout/stderr e file su disco. Nella terminologia della GPL si tratta di
*programmi separati* in *mera aggregazione*, non di *opere derivate*: l'utente
li installa autonomamente tramite il gestore di pacchetti del sistema
operativo, e questo progetto non li ridistribuisce.

Di conseguenza le loro licenze **non si propagano** a questo codice, e la
scelta della GPL-3.0-or-later per questo progetto non impone vincoli aggiuntivi
a chi usa quegli strumenti. Va da sé che chiunque **ridistribuisca** i binari
di terze parti insieme a questo software (per esempio in un'immagine live, un
container o un pacchetto) deve rispettare autonomamente le rispettive licenze,
inclusi gli obblighi di messa a disposizione del codice sorgente.

## Strumenti esterni richiesti a runtime

| Strumento | Progetto | Licenza dichiarata a monte | Ruolo |
| --- | --- | --- | --- |
| `idevice_id`, `ideviceinfo`, `idevicebackup2`, `idevicescreenshot`, `idevicesyslog`, `idevicecrashreport`, `idevicediagnostics`, `ideviceprovision`, `idevicepair` | [libimobiledevice](https://libimobiledevice.org) | LGPL-2.1-or-later (libreria); alcune utility GPL-2.0-or-later | Comunicazione con il dispositivo |
| `ideviceinstaller` | [libimobiledevice](https://github.com/libimobiledevice/ideviceinstaller) | GPL-2.0-or-later | Inventario applicazioni |
| `usbmuxd` | [libimobiledevice](https://github.com/libimobiledevice/usbmuxd) | GPL-2.0-or-later / LGPL-2.1-or-later | Multiplexing USB |
| `ifuse` | [libimobiledevice](https://github.com/libimobiledevice/ifuse) | LGPL-2.1-or-later | Mount AFC |
| `ffmpeg` | [FFmpeg](https://ffmpeg.org) | LGPL-2.1-or-later; GPL-2.0-or-later se compilato con componenti GPL | Assemblaggio video |
| `macFUSE` | [macFUSE](https://macfuse.github.io) | Licenza propria non-OSI (macFUSE 4.x) | Supporto FUSE su macOS |

> Le licenze indicate riflettono quanto dichiarato dai progetti a monte al
> momento della stesura. I singoli pacchetti delle distribuzioni possono
> divergere: verifica con `dpkg -s <pacchetto>` o consultando
> `/usr/share/doc/<pacchetto>/copyright` sulla tua installazione.
> Questo documento è informativo e non costituisce parere legale.

## Attribuzioni

Questo progetto non è affiliato né approvato da Apple Inc. "iPhone", "iPad",
"iOS", "macOS" e "iTunes" sono marchi registrati di Apple Inc., citati
unicamente a fini descrittivi e di interoperabilità.

"Tsurugi Linux" è un marchio dei rispettivi autori, citato a fini descrittivi.

## Nota sulla licenza precedente

Le prime revisioni di questo repository contenevano un file `LICENSE` con il
testo **CC0-1.0**, mentre il README dichiarava GPLv3. L'incoerenza è stata
risolta adottando **GPL-3.0-or-later**, coerentemente con l'intenzione
originaria espressa nel README.

Chi avesse ottenuto una copia del codice mentre era pubblicato sotto CC0-1.0
conserva i diritti concessi da quella licenza su quella specifica copia: CC0 è
irrevocabile. La modifica ha effetto sulle versioni successive. Se il progetto
ha ricevuto contributi esterni durante il periodo CC0, il cambio di licenza è
comunque legittimo, poiché CC0 permette la ridistribuzione dell'opera anche
modificata sotto qualsiasi termine.
