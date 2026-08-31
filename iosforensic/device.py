# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  vo10288
"""Interfaccia verso il dispositivo iOS tramite la suite libimobiledevice.

Tutti gli strumenti esterni sono invocati come processi separati. Nessuna
libreria di terze parti viene importata o collegata a questo codice.
"""

from __future__ import annotations

import datetime
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .config import (
    DEFAULT_TIMEOUT,
    EXTENSION_CATEGORY,
    EXTERNAL_TOOLS,
    LONG_TIMEOUT,
    MEDIA_CATEGORIES,
)


class ToolNotFoundError(RuntimeError):
    """Uno strumento esterno richiesto non è installato."""


class DeviceError(RuntimeError):
    """Un comando verso il dispositivo è fallito."""


@dataclass(frozen=True)
class CommandResult:
    """Esito di un comando esterno."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def check(self) -> CommandResult:
        """Solleva :class:`DeviceError` se il comando è fallito."""
        if not self.ok:
            detail = (self.stderr or self.stdout).strip().splitlines()
            reason = detail[-1] if detail else f"exit code {self.returncode}"
            raise DeviceError(f"{self.command[0]}: {reason}")
        return self


def which(tool: str) -> str | None:
    """Percorso assoluto di uno strumento esterno, se presente nel PATH."""
    return shutil.which(tool)


def check_environment() -> dict[str, dict]:
    """Verifica la presenza degli strumenti esterni."""
    report: dict[str, dict] = {}
    for tool, (required, description) in EXTERNAL_TOOLS.items():
        path = which(tool)
        report[tool] = {
            "path": path,
            "required": required,
            "description": description,
            "available": path is not None,
        }
    return report


def missing_required() -> list[str]:
    """Elenco degli strumenti obbligatori assenti."""
    return [
        tool
        for tool, info in check_environment().items()
        if info["required"] and not info["available"]
    ]


def platform_info() -> dict:
    """Informazioni sulla workstation di acquisizione."""
    system = platform.system()
    info = {
        "system": system,
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "node": platform.node(),
        "is_mac": system == "Darwin",
        "is_linux": system == "Linux",
        "is_tsurugi": False,
    }
    if info["is_linux"]:
        try:
            content = Path("/etc/os-release").read_text(encoding="utf-8").lower()
            info["is_tsurugi"] = "tsurugi" in content
        except OSError:
            pass
    return info


class DeviceInterface:
    """Wrapper sui comandi ``idevice*`` per un singolo dispositivo.

    Args:
        udid: UDID del dispositivo. Se ``None``, i comandi agiscono sul primo
            dispositivo collegato.
        logger: callable ``(event, message, **extra)`` — di norma
            :meth:`iosforensic.case.Case.log` — per tracciare ogni comando
            nell'audit log.
    """

    def __init__(self, udid: str | None = None, logger=None) -> None:
        self.udid = udid
        self.device_info: dict[str, str] = {}
        self._logger = logger

    # ------------------------------------------------------------------ #
    # Esecuzione
    # ------------------------------------------------------------------ #

    def _log(self, event: str, message: str, **extra) -> None:
        if self._logger is not None:
            self._logger(event, message, **extra)

    def run(
        self,
        tool: str,
        *args: str,
        timeout: int = DEFAULT_TIMEOUT,
        with_udid: bool = True,
        input_text: str | None = None,
    ) -> CommandResult:
        """Esegue uno strumento esterno e restituisce l'esito.

        ``-u <udid>`` viene inserito **subito dopo** il nome del programma,
        prima di ogni sottocomando. Le utility libimobiledevice analizzano le
        opzioni con ``getopt``, che si ferma al primo argomento posizionale:
        un ``-u`` messo dopo il sottocomando viene ignorato o interpretato
        come parametro del sottocomando stesso.
        """
        if which(tool) is None:
            raise ToolNotFoundError(
                f"'{tool}' non trovato nel PATH. Esegui 'iosforensic doctor' "
                f"per l'elenco delle dipendenze mancanti."
            )

        command = [tool]
        if with_udid and self.udid:
            command += ["-u", self.udid]
        command += [str(a) for a in args]

        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=input_text,
                check=False,
            )
            stdout, stderr, code = completed.stdout, completed.stderr, completed.returncode
        except subprocess.TimeoutExpired:
            stdout, stderr, code = "", f"timeout dopo {timeout}s", 124
        except OSError as exc:
            stdout, stderr, code = "", f"errore di esecuzione: {exc}", 126

        duration = round(time.monotonic() - started, 3)
        result = CommandResult(command, code, stdout, stderr, duration)
        self._log(
            "command",
            " ".join(command),
            returncode=code,
            duration=duration,
            stderr=stderr.strip()[:500],
        )
        return result

    # ------------------------------------------------------------------ #
    # Rilevamento e pairing
    # ------------------------------------------------------------------ #

    @staticmethod
    def list_devices() -> list[str]:
        """UDID dei dispositivi attualmente collegati via USB."""
        if which("idevice_id") is None:
            raise ToolNotFoundError("'idevice_id' non trovato nel PATH.")
        completed = subprocess.run(
            ["idevice_id", "-l"], capture_output=True, text=True, timeout=30, check=False
        )
        return [line.strip() for line in completed.stdout.splitlines() if line.strip()]

    def detect(self) -> str:
        """Seleziona il primo dispositivo collegato e ne restituisce l'UDID."""
        udids = self.list_devices()
        if not udids:
            raise DeviceError(
                "Nessun dispositivo iOS rilevato. Verifica il cavo USB, sblocca "
                "il dispositivo e tocca 'Autorizza'."
            )
        self.udid = udids[0]
        self._log("device.detected", f"Dispositivo selezionato: {self.udid}")
        if len(udids) > 1:
            self._log(
                "device.multiple",
                f"Rilevati {len(udids)} dispositivi; selezionato il primo",
                others=udids[1:],
            )
        return self.udid

    def is_paired(self) -> bool:
        """Verifica l'esistenza di un pairing record valido."""
        return self.run("idevicepair", "validate", timeout=15).ok

    def pair(self) -> CommandResult:
        """Richiede il pairing. Il dispositivo deve essere sbloccato."""
        self._log("pairing.request", f"Pairing richiesto per {self.udid or 'primo dispositivo'}")
        return self.run("idevicepair", "pair", timeout=60)

    # ------------------------------------------------------------------ #
    # Informazioni
    # ------------------------------------------------------------------ #

    def info(self, domain: str | None = None) -> dict[str, str]:
        """Informazioni del dispositivo come dizionario chiave/valore."""
        args = ["-q", domain] if domain else []
        result = self.run("ideviceinfo", *args, timeout=30).check()
        parsed: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if ": " in line:
                key, _, value = line.partition(": ")
                parsed[key.strip()] = value.strip()
        if domain is None:
            self.device_info = parsed
        return parsed

    def name(self) -> str:
        """Nome assegnato al dispositivo."""
        if which("idevicename") is None:
            return self.device_info.get("DeviceName", "sconosciuto")
        result = self.run("idevicename", timeout=15)
        return result.stdout.strip() if result.ok else "sconosciuto"

    def device_date(self) -> str | None:
        """Data e ora del dispositivo.

        Va confrontata con l'orologio della workstation e annotata: uno
        scostamento rilevante cambia l'interpretazione di ogni timestamp
        presente negli artefatti.
        """
        if which("idevicedate") is None:
            return None
        result = self.run("idevicedate", timeout=15)
        return result.stdout.strip() if result.ok else None

    def clock_skew(self) -> dict[str, str]:
        """Confronto fra l'orologio del dispositivo e quello della workstation."""
        return {
            "device_date": self.device_date() or "non disponibile",
            "workstation_date": datetime.datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
        }

    def summary(self) -> dict[str, str]:
        """Sottoinsieme delle informazioni più rilevanti per il verbale."""
        data = self.info()
        keys = {
            "UniqueDeviceID": "UDID",
            "DeviceName": "Nome dispositivo",
            "ProductType": "Modello",
            "ProductVersion": "Versione iOS",
            "BuildVersion": "Build",
            "SerialNumber": "Numero di serie",
            "WiFiAddress": "MAC WiFi",
            "BluetoothAddress": "MAC Bluetooth",
            "PhoneNumber": "Numero di telefono",
            "InternationalMobileEquipmentIdentity": "IMEI",
            "IntegratedCircuitCardIdentity": "ICCID",
            "TotalDiskCapacity": "Capacità disco",
            "PasswordProtected": "Codice di sblocco",
        }
        summary = {label: data.get(key, "n/d") for key, label in keys.items()}
        skew = self.clock_skew()
        summary["Data dispositivo"] = skew["device_date"]
        summary["Data workstation"] = skew["workstation_date"]
        return summary

    def battery(self) -> dict[str, str]:
        """Stato della batteria."""
        try:
            return self.info(domain="com.apple.mobile.battery")
        except DeviceError:
            return {}

    def storage(self) -> dict[str, str]:
        """Occupazione del disco."""
        try:
            return self.info(domain="com.apple.disk_usage")
        except DeviceError:
            return {}

    def diagnostics(self, diag_type: str = "All") -> str:
        """Output diagnostico grezzo."""
        return self.run("idevicediagnostics", "diagnostics", diag_type, timeout=60).check().stdout

    def activation_state(self) -> str:
        """Stato di attivazione del dispositivo."""
        return self.run("ideviceactivation", "state", timeout=30).check().stdout.strip()

    # ------------------------------------------------------------------ #
    # Applicazioni
    # ------------------------------------------------------------------ #

    def list_apps(self, scope: str = "user") -> list[dict[str, str]]:
        """Inventario delle applicazioni installate.

        Args:
            scope: ``user``, ``system`` o ``all``.
        """
        if scope not in {"user", "system", "all"}:
            raise ValueError("scope deve essere 'user', 'system' o 'all'")

        result = self.run("ideviceinstaller", "list", "-o", f"list_{scope}", timeout=120)
        if not result.ok:
            # Le versioni recenti di ideviceinstaller hanno sostituito
            # '-o list_user' con '--user'; si ritenta con la sintassi nuova.
            flag = {"user": "--user", "system": "--system", "all": "--all"}[scope]
            result = self.run("ideviceinstaller", "list", flag, timeout=120).check()

        apps: list[dict[str, str]] = []
        for raw in result.stdout.splitlines():
            line = raw.strip()
            if not line or line.startswith(("Total:", "CFBundleIdentifier")):
                continue
            if " - " in line:
                bundle_id, _, rest = line.partition(" - ")
                apps.append({"bundle_id": bundle_id.strip(), "name_version": rest.strip()})
            elif ", " in line:
                parts = [p.strip().strip('"') for p in line.split(",")]
                apps.append(
                    {
                        "bundle_id": parts[0],
                        "name_version": " ".join(parts[1:]) if len(parts) > 1 else "",
                    }
                )
        return apps

    @staticmethod
    def format_apps(apps: list[dict[str, str]]) -> str:
        """Rende l'inventario applicazioni in forma tabellare."""
        lines = [f"{'BUNDLE ID':<50} NOME E VERSIONE", "-" * 90]
        lines += [f"{a['bundle_id']:<50} {a['name_version']}" for a in apps]
        lines += ["", f"Totale: {len(apps)} applicazioni"]
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Acquisizione
    # ------------------------------------------------------------------ #

    def set_backup_encryption(self, enabled: bool, password: str) -> CommandResult:
        """Attiva o disattiva la cifratura del backup.

        La password è passata su **stdin** e non compare fra gli argomenti del
        processo: la riga di comando è leggibile da qualunque utente del
        sistema tramite ``ps``, quindi passarla come argomento la esporrebbe.
        Non viene registrata nell'audit log.
        """
        state = "on" if enabled else "off"
        self._log("backup.encryption", f"Cifratura backup impostata su '{state}'")
        return self.run(
            "idevicebackup2",
            "encryption",
            state,
            timeout=60,
            input_text=f"{password}\n{password}\n",
        )

    def backup(self, destination: Path, full: bool = True, progress=None) -> CommandResult:
        """Avvia il backup iTunes-style nella cartella indicata.

        Args:
            destination: cartella di destinazione.
            full: passa ``--full`` a ``idevicebackup2``.
            progress: callable opzionale invocato per ogni riga di output.
        """
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)

        if which("idevicebackup2") is None:
            raise ToolNotFoundError("'idevicebackup2' non trovato nel PATH.")

        command = ["idevicebackup2"]
        if self.udid:
            command += ["-u", self.udid]
        command.append("backup")
        if full:
            command.append("--full")
        command.append(str(destination))

        self._log("backup.start", f"Backup verso {destination}", command=" ".join(command))
        started = time.monotonic()

        # stderr è unito a stdout: leggendo un solo flusso non è possibile che
        # il buffer dell'altro si riempia bloccando il processo figlio, cosa
        # che su un backup lungo produrrebbe uno stallo silenzioso.
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        output: list[str] = []
        try:
            for raw in process.stdout:  # type: ignore[union-attr]
                line = raw.rstrip()
                if line:
                    output.append(line)
                    if progress is not None:
                        progress(line)
        finally:
            process.stdout.close()  # type: ignore[union-attr]
            code = process.wait(timeout=LONG_TIMEOUT)

        duration = round(time.monotonic() - started, 3)
        joined = "\n".join(output)
        self._log(
            "backup.end",
            f"Backup terminato con codice {code} in {duration}s",
            returncode=code,
            duration=duration,
        )
        return CommandResult(command, code, joined, "" if code == 0 else joined, duration)

    def screenshot(self, destination: Path) -> CommandResult:
        """Cattura una schermata in formato PNG o TIFF."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        result = self.run("idevicescreenshot", str(destination), timeout=30)
        if result.ok and not destination.exists():
            return CommandResult(
                result.command, 1, result.stdout, "file non creato", result.duration
            )
        return result

    def syslog(
        self, destination: Path, duration: int = 60, process_filter: str | None = None
    ) -> Path:
        """Cattura il log di sistema per la durata indicata, in secondi."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if which("idevicesyslog") is None:
            raise ToolNotFoundError("'idevicesyslog' non trovato nel PATH.")

        command = ["idevicesyslog"]
        if self.udid:
            command += ["-u", self.udid]
        if process_filter:
            command += ["-m", process_filter]

        self._log("syslog.start", f"Cattura syslog per {duration}s verso {destination}")
        with destination.open("w", encoding="utf-8", errors="replace") as handle:
            process = subprocess.Popen(command, stdout=handle, stderr=subprocess.DEVNULL, text=True)
            try:
                process.wait(timeout=duration)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

        size = destination.stat().st_size
        self._log("syslog.end", f"Syslog salvato ({size} byte)", bytes=size)
        return destination

    def crash_reports(self, destination: Path, keep_on_device: bool = True) -> CommandResult:
        """Estrae i crash report dal dispositivo.

        ``keep_on_device`` aggiunge ``--keep``. Senza quel flag
        ``idevicecrashreport`` **rimuove** i report dal dispositivo dopo la
        copia: il reperto verrebbe alterato in modo irreversibile, e una
        seconda acquisizione da parte di un consulente di controparte non
        troverebbe più nulla. Il valore predefinito è quindi ``True``.
        """
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        args = ["-e"]
        if keep_on_device:
            args.append("--keep")
        else:
            self._log(
                "crash.destructive",
                "ATTENZIONE: estrazione senza --keep, i report saranno rimossi dal dispositivo",
            )
        args.append(str(destination))
        result = self.run("idevicecrashreport", *args, timeout=LONG_TIMEOUT)
        if result.ok:
            count = sum(1 for p in destination.rglob("*") if p.is_file())
            self._log("crash.extracted", f"{count} crash report estratti", count=count)
        return result

    def provisioning_profiles(self, destination: Path) -> dict:
        """Estrae i profili di provisioning installati."""
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)

        listing = self.run("ideviceprovision", "list", timeout=30)
        copied = self.run("ideviceprovision", "copy", str(destination), timeout=60)
        count = len(list(destination.glob("*.mobileprovision")))

        if listing.ok:
            (destination / "profiles_list.txt").write_text(listing.stdout, encoding="utf-8")

        return {
            "list": listing.stdout if listing.ok else listing.stderr,
            "count": count,
            "ok": copied.ok,
            "error": "" if copied.ok else copied.stderr.strip(),
        }

    # ------------------------------------------------------------------ #
    # Accesso AFC (Apple File Conduit)
    # ------------------------------------------------------------------ #

    def mount_afc(self, mount_point: Path, bundle_id: str | None = None) -> CommandResult:
        """Monta il filesystem media via ``ifuse``.

        Args:
            mount_point: cartella su cui montare.
            bundle_id: se indicato, monta i Documents dell'app specificata
                invece della cartella media generale.
        """
        mount_point = Path(mount_point)
        mount_point.mkdir(parents=True, exist_ok=True)

        args: list[str] = []
        if bundle_id:
            args += ["--documents", bundle_id]
        args.append(str(mount_point))

        result = self.run("ifuse", *args, timeout=30)
        if result.ok:
            target = f"app {bundle_id}" if bundle_id else "cartella media"
            self._log("afc.mount", f"AFC montato ({target}) su {mount_point}")
        return result

    def unmount_afc(self, mount_point: Path) -> CommandResult:
        """Smonta il filesystem AFC.

        macOS usa ``umount``, Linux ``fusermount -u``: sono due binari
        diversi, non due nomi dello stesso comando.
        """
        mount_point = Path(mount_point)
        if platform.system() == "Darwin":
            result = self.run("umount", str(mount_point), timeout=30, with_udid=False)
        else:
            result = self.run("fusermount", "-u", str(mount_point), timeout=30, with_udid=False)
        if result.ok:
            self._log("afc.unmount", f"AFC smontato da {mount_point}")
        return result

    @staticmethod
    def scan_afc(mount_point: Path, max_depth: int = 3) -> list[dict]:
        """Elenca i file presenti nel mount AFC, fino alla profondità indicata."""
        mount_point = Path(mount_point)
        entries: list[dict] = []
        base_depth = len(mount_point.parts)

        for path in mount_point.rglob("*"):
            if not path.is_file():
                continue
            if len(path.parts) - base_depth > max_depth:
                continue
            try:
                stat = path.stat()
                mtime = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
                size = stat.st_size
            except OSError:
                mtime, size = "n/d", 0
            extension = path.suffix.lower()
            entries.append(
                {
                    "path": path.relative_to(mount_point).as_posix(),
                    "size": size,
                    "mtime": mtime,
                    "type": EXTENSION_CATEGORY.get(extension, "other"),
                    "ext": extension,
                }
            )
        return entries

    def copy_afc_files(
        self,
        mount_point: Path,
        destination: Path,
        categories: tuple[str, ...] | None = None,
        progress=None,
    ) -> tuple[int, int]:
        """Copia i file dal mount AFC, filtrandoli per categoria.

        Restituisce ``(copiati, errori)``. La struttura di cartelle del
        dispositivo viene preservata: in un'acquisizione il percorso originale
        di un file è esso stesso un dato, non un dettaglio di presentazione.
        """
        mount_point = Path(mount_point)
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)

        wanted: set[str] | None = None
        if categories:
            wanted = set()
            for category in categories:
                wanted.update(MEDIA_CATEGORIES.get(category, ()))

        copied = errors = 0
        files = [p for p in mount_point.rglob("*") if p.is_file()]
        for index, source in enumerate(files, start=1):
            if wanted is not None and source.suffix.lower() not in wanted:
                continue
            target = destination / source.relative_to(mount_point)
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(source, target)
                copied += 1
            except OSError as exc:
                self._log("afc.copy_error", f"{source.name}: {exc}")
                errors += 1
            if progress is not None:
                progress(index, len(files), source.name)

        self._log("afc.copy", f"{copied} file copiati, {errors} errori", copied=copied)
        return copied, errors
