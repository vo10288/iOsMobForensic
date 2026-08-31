# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  vo10288
"""Creazione e gestione del caso forense, con audit log append-only."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .config import CASE_SUBDIRS, DEFAULT_ROOT

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def utc_now() -> str:
    """Timestamp ISO 8601 in UTC, con precisione al secondo."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sanitize(value: str) -> str:
    """Rende una stringa utilizzabile come componente di percorso."""
    cleaned = _SAFE_NAME.sub("_", value.strip()).strip("._-")
    return cleaned or "UNSPEC"


@dataclass
class CaseMetadata:
    """Metadati identificativi del caso."""

    case_number: str
    examiner: str
    notes: str = ""
    organization: str = ""
    created_utc: str = field(default_factory=utc_now)
    tool_version: str = __version__

    def to_dict(self) -> dict:
        return asdict(self)


class Case:
    """Un caso forense su disco.

    Incapsula la struttura di cartelle, i metadati e l'audit log. Ogni
    operazione rilevante va registrata con :meth:`log`, in modo che il report
    finale possa ricostruire la catena di custodia.
    """

    METADATA_FILE = "case.json"
    AUDIT_FILE = "audit.log"

    def __init__(self, path: Path, metadata: CaseMetadata) -> None:
        self.path = Path(path)
        self.metadata = metadata

    # ------------------------------------------------------------------ #
    # Costruttori
    # ------------------------------------------------------------------ #

    @classmethod
    def create(
        cls,
        case_number: str,
        examiner: str,
        notes: str = "",
        organization: str = "",
        root: Path | None = None,
    ) -> Case:
        """Crea un nuovo caso e la relativa struttura di cartelle."""
        root = Path(root) if root else DEFAULT_ROOT
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = root / f"Case_{sanitize(case_number)}_{stamp}"
        path.mkdir(parents=True, exist_ok=False)

        for sub in CASE_SUBDIRS:
            (path / sub).mkdir(parents=True, exist_ok=True)

        metadata = CaseMetadata(
            case_number=case_number,
            examiner=examiner,
            notes=notes,
            organization=organization,
        )
        case = cls(path, metadata)
        case._write_metadata()
        case.log("case.created", f"Caso {case_number} creato da {examiner}")
        return case

    @classmethod
    def load(cls, path: Path) -> Case:
        """Riapre un caso esistente leggendone i metadati."""
        path = Path(path)
        meta_file = path / cls.METADATA_FILE
        if not meta_file.is_file():
            raise FileNotFoundError(f"Metadati del caso non trovati: {meta_file}")
        raw = json.loads(meta_file.read_text(encoding="utf-8"))
        known = set(CaseMetadata.__dataclass_fields__)
        metadata = CaseMetadata(**{k: v for k, v in raw.items() if k in known})
        return cls(path, metadata)

    # ------------------------------------------------------------------ #
    # Percorsi
    # ------------------------------------------------------------------ #

    def dir(self, name: str) -> Path:
        """Restituisce una sottocartella del caso, creandola se assente."""
        target = self.path / name
        target.mkdir(parents=True, exist_ok=True)
        return target

    def artifact(self, subdir: str, filename: str) -> Path:
        """Percorso di un artefatto dentro una sottocartella del caso."""
        return self.dir(subdir) / sanitize(filename)

    # ------------------------------------------------------------------ #
    # Persistenza
    # ------------------------------------------------------------------ #

    def _write_metadata(self) -> None:
        (self.path / self.METADATA_FILE).write_text(
            json.dumps(self.metadata.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def log(self, event: str, message: str, **extra) -> None:
        """Aggiunge una riga JSON all'audit log.

        Il file è aperto in append e sincronizzato su disco a ogni scrittura,
        così che un'interruzione del processo non perda le voci precedenti.
        """
        entry = {"ts": utc_now(), "event": event, "message": message}
        entry.update(extra)
        line = json.dumps(entry, ensure_ascii=False)
        audit = self.path / self.AUDIT_FILE
        with audit.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def audit_entries(self) -> list[dict]:
        """Rilegge l'audit log come lista di dizionari."""
        audit = self.path / self.AUDIT_FILE
        if not audit.is_file():
            return []
        entries: list[dict] = []
        for line in audit.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                entries.append({"ts": "", "event": "parse_error", "message": line})
        return entries

    def __repr__(self) -> str:  # pragma: no cover - solo diagnostica
        return f"<Case {self.metadata.case_number!r} at {self.path}>"
