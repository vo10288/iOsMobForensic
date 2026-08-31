# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  vo10288
"""Analisi statistica del backup iTunes-style ed estrazione dei media.

I file di un backup iOS non cifrato sono memorizzati con nomi opachi (il SHA-1
del percorso originale) dentro sottocartelle a due caratteri. Il tipo reale si
ricava dalla firma dei primi byte, non dall'estensione, che è assente.

Su un backup **cifrato** il contenuto dei file non è leggibile: l'analisi si
limita alle statistiche strutturali, ed è corretto che sia così. La decifratura
richiede la password ed è fuori dallo scopo di questo modulo.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .config import BACKUP_MARKERS, EXTENSION_CATEGORY

#: Firme dei formati più comuni in un backup iOS: offset -> byte -> estensione.
MAGIC_SIGNATURES: tuple[tuple[int, bytes, str], ...] = (
    (0, b"\xff\xd8\xff", ".jpg"),
    (0, b"\x89PNG\r\n\x1a\n", ".png"),
    (0, b"GIF8", ".gif"),
    (0, b"%PDF", ".pdf"),
    (0, b"SQLite format 3\x00", ".sqlite"),
    (0, b"bplist00", ".plist"),
    (0, b"<?xml", ".xml"),
    (0, b"PK\x03\x04", ".zip"),
    (4, b"ftypheic", ".heic"),
    (4, b"ftypheix", ".heic"),
    (4, b"ftypmif1", ".heic"),
    (4, b"ftypqt", ".mov"),
    (4, b"ftypisom", ".mp4"),
    (4, b"ftypmp42", ".mp4"),
    (4, b"ftypM4A", ".m4a"),
    (4, b"ftypM4V", ".m4v"),
)

def detect_type(path: Path, header_size: int = 32) -> str | None:
    """Estensione presunta di un file, dedotta dai byte iniziali."""
    try:
        with Path(path).open("rb") as handle:
            header = handle.read(header_size)
    except OSError:
        return None
    for offset, signature, extension in MAGIC_SIGNATURES:
        if header[offset : offset + len(signature)] == signature:
            return extension
    return None


@dataclass
class BackupStats:
    """Statistiche strutturali di un backup."""

    root: str
    file_count: int = 0
    total_bytes: int = 0
    encrypted: bool | None = None
    by_type: Counter = field(default_factory=Counter)
    by_category: Counter = field(default_factory=Counter)
    largest: list[tuple[str, int]] = field(default_factory=list)
    markers: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "encrypted": self.encrypted,
            "by_type": dict(self.by_type.most_common()),
            "by_category": dict(self.by_category.most_common()),
            "largest": [{"path": p, "size": s} for p, s in self.largest],
            "markers": self.markers,
        }


class BackupAnalyzer:
    """Analizza un backup acquisito e ne estrae i media."""

    def __init__(self, backup_dir: Path) -> None:
        self.backup_dir = Path(backup_dir)
        if not self.backup_dir.is_dir():
            raise NotADirectoryError(f"Cartella di backup non valida: {backup_dir}")

    # ------------------------------------------------------------------ #

    def is_encrypted(self) -> bool | None:
        """Verifica se il backup è cifrato leggendo ``Manifest.plist``.

        Restituisce ``None`` se il manifest non è presente o non è leggibile.
        """
        for manifest in self.backup_dir.rglob("Manifest.plist"):
            try:
                data = manifest.read_bytes()
            except OSError:
                continue
            # Nel plist binario la chiave IsEncrypted è seguita dal valore
            # booleano true (0x09) o false (0x08).
            index = data.find(b"IsEncrypted")
            if index == -1:
                continue
            window = data[index + len(b"IsEncrypted") : index + len(b"IsEncrypted") + 4]
            if b"\x09" in window:
                return True
            if b"\x08" in window:
                return False
        return None

    def analyze(self, top_n: int = 20, progress=None) -> BackupStats:
        """Calcola le statistiche del backup."""
        stats = BackupStats(root=str(self.backup_dir), encrypted=self.is_encrypted())
        stats.markers = dict.fromkeys(BACKUP_MARKERS, False)
        sizes: list[tuple[str, int]] = []

        files = [p for p in self.backup_dir.rglob("*") if p.is_file() and not p.is_symlink()]
        for index, path in enumerate(files, start=1):
            size = path.stat().st_size
            stats.file_count += 1
            stats.total_bytes += size

            if path.name in stats.markers:
                stats.markers[path.name] = True

            # In un backup iOS i file hanno nomi opachi (SHA-1 del percorso
            # originale) e nessuna estensione: filtrare per suffisso, come
            # faceva la versione monolitica, non trova quasi nulla. Il tipo va
            # dedotto dai byte iniziali.
            extension = path.suffix.lower() or detect_type(path) or "(sconosciuto)"
            stats.by_type[extension] += 1
            stats.by_category[EXTENSION_CATEGORY.get(extension, "altro")] += 1
            sizes.append((path.relative_to(self.backup_dir).as_posix(), size))

            if progress is not None:
                progress(index, len(files), path.name)

        sizes.sort(key=lambda item: item[1], reverse=True)
        stats.largest = sizes[:top_n]
        return stats

    def write_analysis(self, destination: Path, top_n: int = 20) -> Path:
        """Salva le statistiche del backup in formato JSON."""
        stats = self.analyze(top_n=top_n)
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(stats.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return destination

    # ------------------------------------------------------------------ #

    def extract_media(
        self,
        destination: Path,
        categories: tuple[str, ...] = ("immagini", "video", "audio"),
        progress=None,
    ) -> dict[str, int]:
        """Copia i media dal backup, ordinandoli per categoria.

        I file sono **copiati**, mai spostati: il backup originale resta
        intatto e riverificabile rispetto al manifest degli hash. Il nome
        opaco originale è conservato come prefisso per poter risalire alla
        voce corrispondente nel database del backup.
        """
        destination = Path(destination)
        counters: Counter[str] = Counter()

        files = [p for p in self.backup_dir.rglob("*") if p.is_file() and not p.is_symlink()]
        for index, path in enumerate(files, start=1):
            extension = path.suffix.lower() or detect_type(path)
            if extension is None:
                continue
            category = EXTENSION_CATEGORY.get(extension)
            if category not in categories:
                continue

            target_dir = destination / category
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"{path.stem}{extension}"

            counter = 1
            while target.exists():
                target = target_dir / f"{path.stem}_{counter}{extension}"
                counter += 1

            target.write_bytes(path.read_bytes())
            counters[category] += 1

            if progress is not None:
                progress(index, len(files), target.name)

        return dict(counters)
