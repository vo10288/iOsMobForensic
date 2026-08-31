# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  vo10288
"""Analisi del log di sistema iOS.

Senza jailbreak non è possibile eseguire ``ps`` sul dispositivo. Questo modulo
ricostruisce in modo **indiziario** quali processi risultavano attivi durante
la finestra di cattura del syslog, a partire dalle righe emesse. Il risultato
va presentato come inferenza, non come inventario esaustivo dei processi.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

#: Riga di syslog iOS. Il livello fra angolari è opzionale: idevicesyslog lo
#: emette solo per alcune sorgenti, e pretenderlo scarterebbe righe valide.
#:
#: Un solo pattern gestisce sia "processo[pid]" sia "processo(subsystem)[pid]",
#: rendendo il sottosistema un gruppo facoltativo. Usare due espressioni
#: separate sulla stessa riga, come nella versione monolitica, contava due
#: volte ogni riga con sottosistema e gonfiava le statistiche.
SYSLOG_LINE = re.compile(
    r"^(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<host>\S+)\s+"
    r"(?P<process>[\w\.\-\+ ]+?)"
    r"(?:\((?P<subsystem>[^)]*)\))?"
    r"\[(?P<pid>\d+)\]"
    r"(?:\s*<(?P<level>\w+)>)?:\s*"
    r"(?P<message>.*)$"
)


@dataclass(frozen=True)
class ProcessObservation:
    """Un processo osservato nel syslog."""

    name: str
    pids: tuple[int, ...]
    occurrences: int
    first_seen: str
    last_seen: str
    levels: dict[str, int]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "pids": list(self.pids),
            "occurrences": self.occurrences,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "levels": self.levels,
        }


class SyslogProcessParser:
    """Estrae le occorrenze dei processi da un file di syslog."""

    def __init__(self, syslog_path: Path) -> None:
        self.syslog_path = Path(syslog_path)
        self.total_lines = 0
        self.parsed_lines = 0

    def parse(self) -> list[ProcessObservation]:
        """Restituisce i processi osservati, ordinati per numero di occorrenze."""
        pids: dict[str, set[int]] = {}
        counts: Counter[str] = Counter()
        first: dict[str, str] = {}
        last: dict[str, str] = {}
        levels: dict[str, Counter[str]] = {}

        self.total_lines = 0
        self.parsed_lines = 0

        with self.syslog_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                self.total_lines += 1
                match = SYSLOG_LINE.match(line.rstrip("\n"))
                if match is None:
                    continue
                self.parsed_lines += 1

                name = match.group("process").strip()
                pid = int(match.group("pid"))
                timestamp = match.group("timestamp")
                level = match.group("level") or "Unspecified"

                pids.setdefault(name, set()).add(pid)
                counts[name] += 1
                first.setdefault(name, timestamp)
                last[name] = timestamp
                levels.setdefault(name, Counter())[level] += 1

        observations = [
            ProcessObservation(
                name=name,
                pids=tuple(sorted(pids[name])),
                occurrences=counts[name],
                first_seen=first[name],
                last_seen=last[name],
                levels=dict(levels[name]),
            )
            for name in counts
        ]
        observations.sort(key=lambda obs: (-obs.occurrences, obs.name))
        return observations

    def write_report(self, destination: Path) -> Path:
        """Scrive un report testuale dei processi osservati."""
        observations = self.parse()
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "ANALISI PROCESSI DA SYSLOG",
            "=" * 70,
            f"Sorgente          : {self.syslog_path.name}",
            f"Righe totali      : {self.total_lines}",
            f"Righe interpretate: {self.parsed_lines}",
            f"Processi distinti : {len(observations)}",
            "",
            "AVVERTENZA: elenco ricostruito dalle righe di log emesse durante la",
            "finestra di cattura. Non equivale all'output di 'ps' e non è",
            "esaustivo: un processo attivo ma silente non compare.",
            "",
            f"{'PROCESSO':<38} {'OCC.':>7}  {'PID':<18} PRIMA VISTA",
            "-" * 88,
        ]
        for obs in observations:
            pid_list = ",".join(str(p) for p in obs.pids[:4])
            if len(obs.pids) > 4:
                pid_list += f",+{len(obs.pids) - 4}"
            lines.append(
                f"{obs.name[:38]:<38} {obs.occurrences:>7}  {pid_list:<18} {obs.first_seen}"
            )

        destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return destination
