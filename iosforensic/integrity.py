# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  vo10288
"""Manifest crittografico degli artefatti e verifica di integrità."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .case import utc_now
from .config import HASH_ALGORITHMS, HASH_CHUNK_SIZE


def hash_file(
    path: Path,
    algorithms: tuple[str, ...] = HASH_ALGORITHMS,
    chunk_size: int = HASH_CHUNK_SIZE,
) -> dict[str, str]:
    """Calcola più digest in una sola lettura del file.

    Leggere il file una volta sola conta: sui backup da decine di gigabyte,
    tre passate separate triplicano il tempo di elaborazione.
    """
    digests = {name: hashlib.new(name) for name in algorithms}
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            for digest in digests.values():
                digest.update(chunk)
    return {name: digest.hexdigest() for name, digest in digests.items()}


@dataclass
class ManifestEntry:
    """Una riga del manifest: un file e i suoi digest."""

    path: str
    size: int
    hashes: dict[str, str]

    def to_dict(self) -> dict:
        return {"path": self.path, "size": self.size, "hashes": self.hashes}


@dataclass
class VerificationResult:
    """Esito del confronto fra manifest e stato attuale del disco."""

    verified: list[str] = field(default_factory=list)
    altered: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)

    @property
    def is_intact(self) -> bool:
        """Vero se nessun file risulta alterato o mancante.

        I file *aggiunti* dopo la creazione del manifest non invalidano gli
        artefatti già acquisiti, ma vengono segnalati a parte.
        """
        return not self.altered and not self.missing

    def summary(self) -> str:
        return (
            f"{len(self.verified)} verificati, {len(self.altered)} alterati, "
            f"{len(self.missing)} mancanti, {len(self.added)} aggiunti"
        )

    def to_dict(self) -> dict:
        return {
            "intact": self.is_intact,
            "verified": self.verified,
            "altered": self.altered,
            "missing": self.missing,
            "added": self.added,
        }


class IntegrityVerifier:
    """Crea e verifica il manifest degli hash di un caso."""

    MANIFEST_JSON = "manifest.json"
    MANIFEST_TXT = "manifest.txt"

    #: File esclusi dal manifest perché mutano per costruzione.
    EXCLUDED = {"audit.log", MANIFEST_JSON, MANIFEST_TXT}

    def __init__(self, case) -> None:
        self.case = case

    # ------------------------------------------------------------------ #

    def _iter_files(self):
        """File del caso da includere nel manifest, in ordine deterministico."""
        hashes_dir = self.case.path / "hashes"
        for path in sorted(self.case.path.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            if path.name in self.EXCLUDED:
                continue
            if hashes_dir in path.parents:
                continue
            yield path

    def build(self, progress=None) -> list[ManifestEntry]:
        """Calcola il manifest dell'intero caso.

        Args:
            progress: callable opzionale ``(indice, totale, percorso)``.
        """
        files = list(self._iter_files())
        entries: list[ManifestEntry] = []
        for index, path in enumerate(files, start=1):
            relative = path.relative_to(self.case.path).as_posix()
            entries.append(
                ManifestEntry(
                    path=relative,
                    size=path.stat().st_size,
                    hashes=hash_file(path),
                )
            )
            if progress is not None:
                progress(index, len(files), relative)

        self._write(entries)
        self.case.log(
            "integrity.manifest",
            f"Manifest creato: {len(entries)} file",
            files=len(entries),
        )
        return entries

    def _write(self, entries: list[ManifestEntry]) -> tuple[Path, Path]:
        hashes_dir = self.case.dir("hashes")

        payload = {
            "case": self.case.metadata.to_dict(),
            "generated_utc": utc_now(),
            "algorithms": list(HASH_ALGORITHMS),
            "file_count": len(entries),
            "total_bytes": sum(entry.size for entry in entries),
            "entries": [entry.to_dict() for entry in entries],
        }
        json_path = hashes_dir / self.MANIFEST_JSON
        json_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        lines = [
            f"# Hash manifest - Caso {self.case.metadata.case_number}",
            f"# Esaminatore: {self.case.metadata.examiner}",
            f"# Generato (UTC): {payload['generated_utc']}",
            f"# File: {len(entries)}  Byte totali: {payload['total_bytes']}",
            "",
        ]
        for entry in entries:
            lines.append(entry.path)
            lines.append(f"  size    {entry.size}")
            for algorithm in HASH_ALGORITHMS:
                lines.append(f"  {algorithm:<7} {entry.hashes[algorithm]}")
            lines.append("")
        txt_path = hashes_dir / self.MANIFEST_TXT
        txt_path.write_text("\n".join(lines), encoding="utf-8")

        return json_path, txt_path

    # ------------------------------------------------------------------ #

    def load_manifest(self) -> dict:
        """Rilegge il manifest JSON del caso."""
        path = self.case.dir("hashes") / self.MANIFEST_JSON
        if not path.is_file():
            raise FileNotFoundError(
                "Manifest non trovato: eseguire prima la creazione del manifest."
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def verify(self, progress=None) -> VerificationResult:
        """Confronta il manifest con lo stato attuale del caso."""
        manifest = self.load_manifest()
        recorded = {entry["path"]: entry for entry in manifest["entries"]}
        result = VerificationResult()

        for index, (relative, entry) in enumerate(sorted(recorded.items()), start=1):
            path = self.case.path / relative
            if not path.is_file():
                result.missing.append(relative)
            else:
                current = hash_file(path, tuple(manifest["algorithms"]))
                if current == entry["hashes"]:
                    result.verified.append(relative)
                else:
                    result.altered.append(relative)
            if progress is not None:
                progress(index, len(recorded), relative)

        on_disk = {
            path.relative_to(self.case.path).as_posix() for path in self._iter_files()
        }
        result.added = sorted(on_disk - set(recorded))

        self.case.log(
            "integrity.verify",
            result.summary(),
            intact=result.is_intact,
            **{k: len(v) for k, v in result.to_dict().items() if isinstance(v, list)},
        )
        return result
