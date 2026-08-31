# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  vo10288
"""Interfaccia grafica tkinter.

Ogni operazione lunga viene eseguita in un thread separato e comunica con
l'interfaccia tramite una coda: tkinter non è thread-safe, quindi solo il
thread principale tocca i widget. È il motivo per cui una GUI che invoca
``subprocess.run`` direttamente nel callback di un pulsante si blocca durante
un backup da trenta minuti.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import __version__
from ..backup import BackupAnalyzer
from ..case import Case
from ..device import DeviceInterface, check_environment
from ..integrity import IntegrityVerifier
from ..parsers import SyslogProcessParser
from ..report import ForensicReportGenerator, human_size


class WorkerMixin:
    """Esecuzione di operazioni in background con log sull'interfaccia."""

    def __init__(self) -> None:
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._busy = False

    def _pump(self) -> None:
        """Svuota la coda dei messaggi provenienti dai thread di lavoro."""
        while True:
            try:
                kind, payload = self._queue.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self.log(str(payload))
            elif kind == "error":
                self._busy = False
                messagebox.showerror("Errore", str(payload))
            elif kind == "done":
                self._busy = False
                self.log(str(payload))
        self.root.after(120, self._pump)

    def run_async(self, description: str, function, *args, **kwargs) -> None:
        """Esegue ``function`` in un thread, riportando esito e messaggi."""
        if self._busy:
            messagebox.showwarning("Operazione in corso", "Attendi il completamento.")
            return
        self._busy = True
        self.log(f"▶ {description}")

        def target() -> None:
            try:
                result = function(*args, **kwargs)
                self._queue.put(("done", f"✔ {description}: {result}"))
            except Exception as exc:  # noqa: BLE001 - riportato all'utente
                self._queue.put(("error", f"{description}\n\n{exc}"))

        threading.Thread(target=target, daemon=True).start()

    def emit(self, message: str) -> None:
        """Invia un messaggio dall'interno di un thread di lavoro."""
        self._queue.put(("log", message))


class ForensicApp(WorkerMixin):
    """Finestra principale."""

    def __init__(self) -> None:
        WorkerMixin.__init__(self)
        self.case: Case | None = None
        self.device = DeviceInterface()

        self.root = tk.Tk()
        self.root.title(f"iOS Forensic Acquisition Tool {__version__}")
        self.root.geometry("1000x720")

        self._build_toolbar()
        self._build_tabs()
        self._build_log()
        self._pump()

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.root, padding=8)
        bar.pack(fill="x")

        ttk.Button(bar, text="Rileva dispositivo", command=self.detect_device).pack(side="left")
        ttk.Button(bar, text="Pair", command=self.pair_device).pack(side="left", padx=4)
        ttk.Button(bar, text="Verifica dipendenze", command=self.show_doctor).pack(side="left")

        self.status = tk.StringVar(value="Nessun dispositivo — nessun caso aperto")
        ttk.Label(bar, textvariable=self.status).pack(side="right")

    def _build_tabs(self) -> None:
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=4)

        self._tab_case()
        self._tab_acquisition()
        self._tab_files()
        self._tab_analysis()

    def _tab_case(self) -> None:
        frame = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(frame, text="Caso")

        self.var_case = tk.StringVar()
        self.var_examiner = tk.StringVar()
        self.var_org = tk.StringVar()
        self.var_notes = tk.StringVar()

        fields = (
            ("Numero caso", self.var_case),
            ("Esaminatore", self.var_examiner),
            ("Organizzazione", self.var_org),
            ("Note", self.var_notes),
        )
        for row, (label, variable) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(frame, textvariable=variable, width=52).grid(
                row=row, column=1, sticky="w", padx=8
            )

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=12)
        ttk.Button(buttons, text="Inizializza caso", command=self.create_case).pack(side="left")
        ttk.Button(buttons, text="Apri caso esistente", command=self.open_case).pack(
            side="left", padx=6
        )

    def _tab_acquisition(self) -> None:
        frame = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(frame, text="Acquisizione")

        self.var_encrypted = tk.BooleanVar(value=True)
        self.var_syslog_duration = tk.IntVar(value=60)

        ttk.Button(frame, text="Info dispositivo", command=self.acquire_info).grid(
            row=0, column=0, sticky="ew", pady=3
        )
        ttk.Button(frame, text="Lista applicazioni", command=self.acquire_apps).grid(
            row=1, column=0, sticky="ew", pady=3
        )
        ttk.Button(frame, text="Backup completo", command=self.acquire_backup).grid(
            row=2, column=0, sticky="ew", pady=3
        )
        ttk.Checkbutton(frame, text="Backup cifrato (raccomandato)",
                        variable=self.var_encrypted).grid(row=2, column=1, sticky="w", padx=10)

        ttk.Button(frame, text="Screenshot", command=self.acquire_screenshot).grid(
            row=3, column=0, sticky="ew", pady=3
        )
        ttk.Button(frame, text="Cattura syslog", command=self.acquire_syslog).grid(
            row=4, column=0, sticky="ew", pady=3
        )
        spin = ttk.Spinbox(
            frame, from_=10, to=600, increment=10, width=6,
            textvariable=self.var_syslog_duration,
        )
        spin.grid(row=4, column=1, sticky="w", padx=10)
        ttk.Label(frame, text="secondi").grid(row=4, column=2, sticky="w")

        ttk.Button(frame, text="Crash report", command=self.acquire_crash).grid(
            row=5, column=0, sticky="ew", pady=3
        )
        frame.columnconfigure(0, minsize=220)

    def _tab_files(self) -> None:
        frame = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(frame, text="File e media (AFC)")

        self.var_mount_point = tk.StringVar(value="/tmp/ios_afc")
        self.var_bundle_id = tk.StringVar()

        ttk.Label(frame, text="Punto di mount").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.var_mount_point, width=40).grid(
            row=0, column=1, sticky="w", padx=8
        )
        ttk.Label(frame, text="Bundle ID (opzionale)").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.var_bundle_id, width=40).grid(
            row=1, column=1, sticky="w", padx=8
        )

        actions = (
            ("Monta AFC", self.mount_afc),
            ("Scansiona file", self.scan_afc),
            ("Copia media nel caso", self.copy_afc),
            ("Smonta AFC", self.unmount_afc),
            ("Estrai provisioning profile", self.acquire_provisioning),
        )
        for offset, (label, command) in enumerate(actions):
            ttk.Button(frame, text=label, command=command).grid(
                row=2 + offset, column=0, sticky="ew", pady=3
            )
        frame.columnconfigure(0, minsize=240)

    def mount_afc(self) -> None:
        if self.require_case() is None:
            return
        bundle = self.var_bundle_id.get().strip() or None
        mount_point = Path(self.var_mount_point.get())
        self.run_async(
            "Mount AFC",
            lambda: str(self.device.mount_afc(mount_point, bundle_id=bundle).check().ok),
        )

    def scan_afc(self) -> None:
        case = self.require_case()
        if case is None:
            return
        mount_point = Path(self.var_mount_point.get())

        def task() -> str:
            import json

            entries = self.device.scan_afc(mount_point)
            case.artifact("afc_media", "afc_scan.json").write_text(
                json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            counts: dict[str, int] = {}
            for entry in entries:
                counts[entry["type"]] = counts.get(entry["type"], 0) + 1
            for kind, count in sorted(counts.items()):
                self.emit(f"    {kind}: {count}")
            return f"{len(entries)} file rilevati"

        self.run_async("Scansione AFC", task)

    def copy_afc(self) -> None:
        case = self.require_case()
        if case is None:
            return
        mount_point = Path(self.var_mount_point.get())

        def task() -> str:
            copied, errors = self.device.copy_afc_files(
                mount_point,
                case.dir("afc_media"),
                categories=("images", "videos", "audio"),
            )
            return f"{copied} file copiati, {errors} errori"

        self.run_async("Copia media via AFC", task)

    def unmount_afc(self) -> None:
        mount_point = Path(self.var_mount_point.get())
        self.run_async("Smontaggio AFC", lambda: str(self.device.unmount_afc(mount_point).ok))

    def acquire_provisioning(self) -> None:
        case = self.require_case()
        if case is None:
            return

        def task() -> str:
            result = self.device.provisioning_profiles(case.dir("provisioning_profiles"))
            return f"{result['count']} profili estratti"

        self.run_async("Estrazione provisioning profile", task)

    def _tab_analysis(self) -> None:
        frame = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(frame, text="Analisi e integrità")

        actions = (
            ("Analizza backup", self.analyze_backup),
            ("Estrai media dal backup", self.extract_media),
            ("Analizza processi da syslog", self.analyze_processes),
            ("Crea manifest hash", self.build_manifest),
            ("Verifica integrità", self.verify_manifest),
            ("Genera report forense", self.generate_report),
        )
        for row, (label, command) in enumerate(actions):
            ttk.Button(frame, text=label, command=command).grid(
                row=row, column=0, sticky="ew", pady=3
            )
        frame.columnconfigure(0, minsize=260)

    def _build_log(self) -> None:
        frame = ttk.LabelFrame(self.root, text="Registro operazioni", padding=6)
        frame.pack(fill="both", expand=False, padx=8, pady=(0, 8))

        self.log_widget = tk.Text(frame, height=12, wrap="word", state="disabled")
        scrollbar = ttk.Scrollbar(frame, command=self.log_widget.yview)
        self.log_widget.configure(yscrollcommand=scrollbar.set)
        self.log_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    # ------------------------------------------------------------------ #
    # Utilità
    # ------------------------------------------------------------------ #

    def log(self, message: str) -> None:
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", message + "\n")
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")

    def require_case(self) -> Case | None:
        if self.case is None:
            messagebox.showwarning("Nessun caso", "Inizializza o apri prima un caso.")
        return self.case

    def _refresh_status(self) -> None:
        device = self.device.udid or "nessun dispositivo"
        case = self.case.metadata.case_number if self.case else "nessun caso"
        self.status.set(f"{device}  |  caso: {case}")

    # ------------------------------------------------------------------ #
    # Azioni
    # ------------------------------------------------------------------ #

    def show_doctor(self) -> None:
        lines = [
            f"{'presente' if info['available'] else 'MANCANTE':<9} {tool:<22} "
            f"{'richiesto' if info['required'] else 'opzionale'}"
            for tool, info in check_environment().items()
        ]
        messagebox.showinfo("Dipendenze esterne", "\n".join(lines))

    def detect_device(self) -> None:
        udids = DeviceInterface.list_devices()
        if not udids:
            messagebox.showwarning(
                "Nessun dispositivo",
                "Verifica il cavo USB, sblocca il dispositivo e tocca 'Autorizza'.",
            )
            return
        self.device = DeviceInterface(
            udid=udids[0], logger=self.case.log if self.case else None
        )
        self.log(f"Dispositivo rilevato: {udids[0]}")
        if len(udids) > 1:
            self.log(f"Altri dispositivi collegati: {', '.join(udids[1:])}")
        self._refresh_status()

    def pair_device(self) -> None:
        result = self.device.pair()
        self.log("Pairing riuscito." if result.ok else f"Pairing fallito: {result.stderr.strip()}")

    def create_case(self) -> None:
        if not self.var_case.get().strip() or not self.var_examiner.get().strip():
            messagebox.showwarning("Dati mancanti", "Numero caso ed esaminatore sono obbligatori.")
            return
        self.case = Case.create(
            case_number=self.var_case.get().strip(),
            examiner=self.var_examiner.get().strip(),
            organization=self.var_org.get().strip(),
            notes=self.var_notes.get().strip(),
        )
        self.device = DeviceInterface(udid=self.device.udid, logger=self.case.log)
        self.log(f"Caso creato: {self.case.path}")
        self._refresh_status()

    def open_case(self) -> None:
        selected = filedialog.askdirectory(title="Seleziona la cartella del caso")
        if not selected:
            return
        self.case = Case.load(Path(selected))
        self.device = DeviceInterface(udid=self.device.udid, logger=self.case.log)
        self.var_case.set(self.case.metadata.case_number)
        self.var_examiner.set(self.case.metadata.examiner)
        self.log(f"Caso aperto: {self.case.path}")
        self._refresh_status()

    # -- acquisizione --------------------------------------------------- #

    def acquire_info(self) -> None:
        case = self.require_case()
        if case is None:
            return

        def task() -> str:
            import json

            summary = self.device.summary()
            case.artifact("device_info", "device_info.json").write_text(
                json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            for key, value in summary.items():
                self.emit(f"    {key}: {value}")
            return "informazioni salvate"

        self.run_async("Acquisizione info dispositivo", task)

    def acquire_apps(self) -> None:
        case = self.require_case()
        if case is None:
            return

        def task() -> str:
            apps = self.device.list_apps(scope="all")
            target = case.artifact("app_list", "apps_all.txt")
            target.write_text(self.device.format_apps(apps), encoding="utf-8")
            return f"{len(apps)} applicazioni salvate"

        self.run_async("Inventario applicazioni", task)

    def acquire_backup(self) -> None:
        case = self.require_case()
        if case is None:
            return
        if self.var_encrypted.get():
            messagebox.showinfo(
                "Backup cifrato",
                "Imposta la cifratura del backup dal dispositivo o via CLI\n"
                "('iosforensic backup --encrypted'), così la password non\n"
                "transita per l'interfaccia grafica. Annotala nel verbale.",
            )

        def task() -> str:
            result = self.device.backup(case.dir("backup"))
            if not result.ok:
                raise RuntimeError(result.stderr.strip()[:400])
            return "backup completato"

        self.run_async("Acquisizione backup", task)

    def acquire_screenshot(self) -> None:
        case = self.require_case()
        if case is None:
            return
        from datetime import datetime

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = case.artifact("screenshots", f"screenshot_{stamp}.png")
        self.run_async("Cattura schermo", lambda: str(self.device.screenshot(target).ok))

    def acquire_syslog(self) -> None:
        case = self.require_case()
        if case is None:
            return
        duration = self.var_syslog_duration.get()

        def task() -> str:
            target = case.artifact("syslog", "syslog.txt")
            self.device.syslog(target, duration=duration)
            return f"{human_size(target.stat().st_size)} catturati"

        self.run_async(f"Cattura syslog ({duration}s)", task)

    def acquire_crash(self) -> None:
        case = self.require_case()
        if case is None:
            return
        self.run_async(
            "Estrazione crash report",
            lambda: str(self.device.crash_reports(case.dir("crash_reports")).ok),
        )

    # -- analisi -------------------------------------------------------- #

    def analyze_backup(self) -> None:
        case = self.require_case()
        if case is None:
            return

        def task() -> str:
            analyzer = BackupAnalyzer(case.dir("backup"))
            stats = analyzer.analyze()
            analyzer.write_analysis(case.artifact("reports", "analisi_backup.json"))
            for category, count in stats.by_category.most_common():
                self.emit(f"    {category}: {count}")
            return f"{stats.file_count} file, {human_size(stats.total_bytes)}"

        self.run_async("Analisi backup", task)

    def extract_media(self) -> None:
        case = self.require_case()
        if case is None:
            return

        def task() -> str:
            analyzer = BackupAnalyzer(case.dir("backup"))
            counters = analyzer.extract_media(case.dir("backup_media"))
            return ", ".join(f"{k}: {v}" for k, v in counters.items()) or "nessun media"

        self.run_async("Estrazione media dal backup", task)

    def analyze_processes(self) -> None:
        case = self.require_case()
        if case is None:
            return

        def task() -> str:
            syslog = case.dir("syslog") / "syslog.txt"
            if not syslog.is_file():
                raise FileNotFoundError("Nessun syslog catturato in questo caso.")
            parser = SyslogProcessParser(syslog)
            parser.write_report(case.artifact("syslog", "processi.txt"))
            return f"{parser.parsed_lines}/{parser.total_lines} righe interpretate"

        self.run_async("Analisi processi da syslog", task)

    def build_manifest(self) -> None:
        case = self.require_case()
        if case is None:
            return

        def task() -> str:
            entries = IntegrityVerifier(case).build()
            return f"{len(entries)} file hashati"

        self.run_async("Creazione manifest hash", task)

    def verify_manifest(self) -> None:
        case = self.require_case()
        if case is None:
            return

        def task() -> str:
            result = IntegrityVerifier(case).verify()
            for item in result.altered:
                self.emit(f"    ALTERATO: {item}")
            for item in result.missing:
                self.emit(f"    MANCANTE: {item}")
            return result.summary()

        self.run_async("Verifica integrità", task)

    def generate_report(self) -> None:
        case = self.require_case()
        if case is None:
            return

        def task() -> str:
            html_path, _ = ForensicReportGenerator(case).generate()
            return str(html_path)

        self.run_async("Generazione report forense", task)

    # ------------------------------------------------------------------ #

    def run(self) -> int:
        self.log(f"iOS Forensic Acquisition Tool {__version__} — GPL-3.0-or-later")
        self.log("Software distribuito senza alcuna garanzia.\n")
        self.root.mainloop()
        return 0


def main() -> int:
    return ForensicApp().run()


if __name__ == "__main__":
    raise SystemExit(main())
