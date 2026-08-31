# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  vo10288
"""Registrazione dello schermo tramite screenshot sequenziali.

iOS non espone un canale di screen recording a ``libimobiledevice``. La
registrazione è quindi ottenuta catturando screenshot a intervalli regolari e
assemblandoli con ``ffmpeg``. Il frame rate reale dipende dalla latenza USB e
del dispositivo: il video prodotto è una ricostruzione, non una cattura
temporalmente fedele. Ogni frame è conservato con il proprio timestamp, ed è il
frame — non il video — a costituire l'artefatto di riferimento.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .device import DeviceInterface, ToolNotFoundError, which


@dataclass
class RecordingResult:
    """Esito di una sessione di registrazione."""

    frames_dir: Path
    frame_count: int
    duration: float
    video_path: Path | None = None
    effective_fps: float = 0.0


class ScreenRecorder:
    """Cattura frame a intervalli regolari e li assembla in video."""

    def __init__(self, device: DeviceInterface, frames_dir: Path) -> None:
        self.device = device
        self.frames_dir = Path(frames_dir)
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._result: RecordingResult | None = None

    # ------------------------------------------------------------------ #

    def _capture_loop(self, interval: float, max_duration: float) -> None:
        started = time.monotonic()
        index = 0
        while not self._stop.is_set():
            if time.monotonic() - started >= max_duration:
                break
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
            target = self.frames_dir / f"frame_{index:06d}_{stamp}.png"
            result = self.device.screenshot(target)
            if result.ok:
                index += 1
            # In caso di errore si continua: un frame perso non deve
            # interrompere l'intera sessione.
            self._stop.wait(interval)

        elapsed = time.monotonic() - started
        self._result = RecordingResult(
            frames_dir=self.frames_dir,
            frame_count=index,
            duration=round(elapsed, 2),
            effective_fps=round(index / elapsed, 2) if elapsed > 0 else 0.0,
        )

    def start(self, interval: float = 0.5, max_duration: float = 300.0) -> None:
        """Avvia la cattura in un thread separato."""
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("Registrazione già in corso.")
        self._stop.clear()
        self._result = None
        self._thread = threading.Thread(
            target=self._capture_loop, args=(interval, max_duration), daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 30.0) -> RecordingResult:
        """Interrompe la cattura e restituisce l'esito."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        if self._result is None:
            raise RuntimeError("Nessuna registrazione completata.")
        return self._result

    @property
    def is_recording(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------ #

    def build_video(self, output: Path, fps: float | None = None) -> Path:
        """Assembla i frame catturati in un file video con ``ffmpeg``.

        Se ``fps`` non è indicato viene usato il frame rate effettivo della
        sessione, così che la durata del video corrisponda a quella reale
        della cattura.
        """
        if which("ffmpeg") is None:
            raise ToolNotFoundError(
                "'ffmpeg' non trovato nel PATH: i frame restano comunque "
                "disponibili come artefatti singoli."
            )

        frames = sorted(self.frames_dir.glob("frame_*.png"))
        if not frames:
            raise FileNotFoundError("Nessun frame da assemblare.")

        if fps is None:
            fps = self._result.effective_fps if self._result else 2.0
        fps = max(fps, 0.1)

        # Elenco esplicito dei frame: il demuxer 'concat' evita di dover
        # rinominare i file in una sequenza numerica contigua.
        listing = self.frames_dir / "frames.txt"
        listing.write_text(
            "\n".join(f"file '{frame.name}'\nduration {1 / fps:.4f}" for frame in frames)
            + f"\nfile '{frames[-1].name}'\n",
            encoding="utf-8",
        )

        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)

        self.device.run(
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(listing),
            "-vsync", "vfr",
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            str(output),
            timeout=1800,
            with_udid=False,
        ).check()

        if self._result is not None:
            self._result.video_path = output
        return output
