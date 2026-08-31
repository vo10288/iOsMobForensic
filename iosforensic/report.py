# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  vo10288
"""Generazione del report forense in HTML e testo semplice."""

from __future__ import annotations

import html
import json
import platform
from pathlib import Path

from . import __version__
from .case import Case, utc_now


def human_size(num_bytes: float) -> str:
    """Dimensione leggibile, con unità binarie."""
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(num_bytes) < 1024 or unit == "TiB":
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{int(num_bytes)} B"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TiB"


CSS = """
body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
       margin: 0 auto; max-width: 62rem; padding: 2rem 1.5rem; color: #1a1a1a;
       line-height: 1.55; }
h1 { border-bottom: 3px solid #1a1a1a; padding-bottom: .4rem; }
h2 { margin-top: 2.5rem; border-bottom: 1px solid #ccc; padding-bottom: .3rem; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: .9rem; }
th, td { border: 1px solid #d0d0d0; padding: .45rem .6rem; text-align: left;
         vertical-align: top; }
th { background: #f2f2f2; font-weight: 600; }
tr:nth-child(even) td { background: #fafafa; }
code, .mono { font-family: ui-monospace, "SFMono-Regular", Menlo, monospace;
              font-size: .82rem; word-break: break-all; }
.ok { color: #0a6b2d; font-weight: 600; }
.warn { color: #a35a00; font-weight: 600; }
.err { color: #9b1c1c; font-weight: 600; }
footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #ccc;
         font-size: .8rem; color: #555; }
"""


class ForensicReportGenerator:
    """Compone il report finale a partire dallo stato del caso."""

    def __init__(self, case: Case) -> None:
        self.case = case

    # ------------------------------------------------------------------ #
    # Raccolta dati
    # ------------------------------------------------------------------ #

    def collect(self) -> dict:
        """Raccoglie i dati da inserire nel report."""
        artifacts = []
        total = 0
        for path in sorted(self.case.path.rglob("*")):
            if path.is_file() and not path.is_symlink():
                size = path.stat().st_size
                total += size
                artifacts.append(
                    {"path": path.relative_to(self.case.path).as_posix(), "size": size}
                )

        manifest_path = self.case.path / "hashes" / "manifest.json"
        manifest = None
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                manifest = None

        device_json = self.case.path / "device_info" / "device_info.json"
        device = {}
        if device_json.is_file():
            try:
                device = json.loads(device_json.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                device = {}

        return {
            "case": self.case.metadata.to_dict(),
            "generated_utc": utc_now(),
            "workstation": {
                "sistema": f"{platform.system()} {platform.release()}",
                "architettura": platform.machine(),
                "python": platform.python_version(),
                "hostname": platform.node(),
                "tool": f"iOS Forensic Acquisition Tool {__version__}",
            },
            "device": device,
            "artifacts": artifacts,
            "artifact_count": len(artifacts),
            "total_bytes": total,
            "manifest": manifest,
            "audit": self.case.audit_entries(),
        }

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #

    @staticmethod
    def _rows(pairs) -> str:
        return "\n".join(
            f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>"
            for k, v in pairs
        )

    def render_html(self, data: dict) -> str:
        meta = data["case"]
        title = f"Report forense — Caso {meta['case_number']}"

        artifacts = "\n".join(
            f"<tr><td class='mono'>{html.escape(a['path'])}</td>"
            f"<td>{human_size(a['size'])}</td></tr>"
            for a in data["artifacts"]
        )

        if data["manifest"]:
            manifest_rows = "\n".join(
                f"<tr><td class='mono'>{html.escape(e['path'])}</td>"
                f"<td class='mono'>{html.escape(e['hashes'].get('sha256', ''))}</td></tr>"
                for e in data["manifest"]["entries"]
            )
            manifest_section = (
                f"<p>Manifest generato il {html.escape(data['manifest']['generated_utc'])} "
                f"su {data['manifest']['file_count']} file "
                f"({human_size(data['manifest']['total_bytes'])}). "
                f"Algoritmi: {', '.join(data['manifest']['algorithms'])}.</p>"
                f"<table><tr><th>File</th><th>SHA-256</th></tr>{manifest_rows}</table>"
            )
        else:
            manifest_section = (
                "<p class='warn'>Nessun manifest degli hash presente. "
                "L'integrità degli artefatti non è verificabile.</p>"
            )

        audit_rows = "\n".join(
            f"<tr><td class='mono'>{html.escape(e.get('ts', ''))}</td>"
            f"<td>{html.escape(e.get('event', ''))}</td>"
            f"<td class='mono'>{html.escape(e.get('message', ''))}</td></tr>"
            for e in data["audit"]
        )

        device_section = (
            f"<table>{self._rows(data['device'].items())}</table>"
            if data["device"]
            else "<p class='warn'>Informazioni del dispositivo non acquisite.</p>"
        )

        return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
<h1>{html.escape(title)}</h1>

<h2>1. Identificazione del caso</h2>
<table>{self._rows([
    ("Numero caso", meta["case_number"]),
    ("Esaminatore", meta["examiner"]),
    ("Organizzazione", meta["organization"] or "n/d"),
    ("Apertura caso (UTC)", meta["created_utc"]),
    ("Report generato (UTC)", data["generated_utc"]),
    ("Cartella del caso", self.case.path),
    ("Note", meta["notes"] or "n/d"),
])}</table>

<h2>2. Workstation di acquisizione</h2>
<table>{self._rows(data["workstation"].items())}</table>

<h2>3. Dispositivo</h2>
{device_section}

<h2>4. Artefatti acquisiti</h2>
<p>{data['artifact_count']} file, {human_size(data['total_bytes'])} complessivi.</p>
<table><tr><th>Percorso</th><th>Dimensione</th></tr>{artifacts}</table>

<h2>5. Integrità</h2>
{manifest_section}

<h2>6. Catena di custodia</h2>
<p>Registro cronologico delle operazioni. I timestamp sono in UTC.</p>
<table><tr><th>Timestamp</th><th>Evento</th><th>Dettaglio</th></tr>{audit_rows}</table>

<h2>7. Limiti dell'acquisizione</h2>
<ul>
<li>L'acquisizione è di tipo <strong>logico</strong>: comprende gli artefatti
esposti dal dispositivo tramite i canali ufficiali, non l'intero file system.</li>
<li>Il pairing con la workstation crea un record sul dispositivo: si tratta
dell'unica modifica indotta dallo strumento sul reperto.</li>
<li>L'eventuale analisi dei processi da syslog è una ricostruzione indiziaria
e non equivale all'elenco dei processi attivi.</li>
<li>Dati protetti da Data Protection di classe più elevata possono non essere
inclusi in un backup non cifrato.</li>
</ul>

<footer>
Prodotto da iOS Forensic Acquisition Tool {__version__} — GPL-3.0-or-later.
Software distribuito senza alcuna garanzia. L'interpretazione dei risultati
resta responsabilità dell'esaminatore.
</footer>
</body>
</html>
"""

    def render_text(self, data: dict) -> str:
        meta = data["case"]
        lines = [
            "=" * 78,
            f"REPORT FORENSE — CASO {meta['case_number']}",
            "=" * 78,
            "",
            "1. IDENTIFICAZIONE",
            "-" * 78,
            f"Numero caso           : {meta['case_number']}",
            f"Esaminatore           : {meta['examiner']}",
            f"Organizzazione        : {meta['organization'] or 'n/d'}",
            f"Apertura caso (UTC)   : {meta['created_utc']}",
            f"Report generato (UTC) : {data['generated_utc']}",
            f"Cartella del caso     : {self.case.path}",
            f"Note                  : {meta['notes'] or 'n/d'}",
            "",
            "2. WORKSTATION",
            "-" * 78,
        ]
        lines += [f"{k.capitalize():<22}: {v}" for k, v in data["workstation"].items()]

        lines += ["", "3. DISPOSITIVO", "-" * 78]
        if data["device"]:
            lines += [f"{k:<22}: {v}" for k, v in data["device"].items()]
        else:
            lines.append("Informazioni non acquisite.")

        lines += [
            "",
            "4. ARTEFATTI",
            "-" * 78,
            f"{data['artifact_count']} file, {human_size(data['total_bytes'])} complessivi.",
            "",
        ]
        lines += [f"  {a['path']}  ({human_size(a['size'])})" for a in data["artifacts"]]

        lines += ["", "5. INTEGRITÀ", "-" * 78]
        if data["manifest"]:
            lines.append(
                f"Manifest del {data['manifest']['generated_utc']} — "
                f"{data['manifest']['file_count']} file, "
                f"algoritmi: {', '.join(data['manifest']['algorithms'])}."
            )
            lines += [
                f"  {e['hashes'].get('sha256', '')}  {e['path']}"
                for e in data["manifest"]["entries"]
            ]
        else:
            lines.append("ATTENZIONE: nessun manifest degli hash presente.")

        lines += ["", "6. CATENA DI CUSTODIA", "-" * 78]
        lines += [
            f"  {e.get('ts', ''):<26} {e.get('event', ''):<22} {e.get('message', '')}"
            for e in data["audit"]
        ]

        lines += [
            "",
            "7. LIMITI",
            "-" * 78,
            "- Acquisizione logica: non comprende l'intero file system.",
            "- Il pairing crea un record sul dispositivo (unica modifica indotta).",
            "- L'analisi processi da syslog è indiziaria, non equivale a 'ps'.",
            "- Un backup non cifrato può escludere dati a protezione elevata.",
            "",
            "=" * 78,
            f"iOS Forensic Acquisition Tool {__version__} — GPL-3.0-or-later",
            "Software distribuito SENZA ALCUNA GARANZIA.",
            "=" * 78,
            "",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------ #

    def generate(self) -> tuple[Path, Path]:
        """Scrive il report HTML e TXT nella cartella ``reports``."""
        data = self.collect()
        reports = self.case.dir("reports")

        html_path = reports / f"report_{self.case.metadata.case_number}.html"
        txt_path = reports / f"report_{self.case.metadata.case_number}.txt"

        html_path.write_text(self.render_html(data), encoding="utf-8")
        txt_path.write_text(self.render_text(data), encoding="utf-8")

        self.case.log("report.generated", f"Report generato: {html_path.name}, {txt_path.name}")
        return html_path, txt_path
