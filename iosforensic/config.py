# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  vo10288
"""Costanti e configurazione condivisa."""

from __future__ import annotations

from pathlib import Path

#: Radice predefinita in cui vengono creati i casi.
DEFAULT_ROOT = Path.home() / "iOS_Forensic_Acquisitions"

#: Algoritmi di hash calcolati per ogni artefatto.
HASH_ALGORITHMS = ("md5", "sha1", "sha256")

#: Dimensione del blocco di lettura durante l'hashing (1 MiB).
HASH_CHUNK_SIZE = 1024 * 1024

#: Sottocartelle create in ogni caso.
CASE_SUBDIRS = (
    "backup",
    "backup_media",
    "device_info",
    "screenshots",
    "screen_recording/frames",
    "syslog",
    "crash_reports",
    "app_list",
    "diagnostics",
    "provisioning_profiles",
    "afc_media",
    "reports",
    "hashes",
)

#: Strumenti esterni: nome eseguibile -> (obbligatorio, descrizione).
EXTERNAL_TOOLS: dict[str, tuple[bool, str]] = {
    "idevice_id": (True, "Elenco dei dispositivi collegati"),
    "idevicepair": (True, "Gestione del pairing"),
    "ideviceinfo": (True, "Informazioni sul dispositivo"),
    "idevicebackup2": (True, "Acquisizione del backup"),
    "idevicename": (False, "Nome del dispositivo"),
    "ideviceinstaller": (False, "Inventario delle applicazioni"),
    "idevicescreenshot": (False, "Cattura schermo"),
    "idevicesyslog": (False, "Cattura del log di sistema"),
    "idevicecrashreport": (False, "Estrazione dei crash report"),
    "idevicediagnostics": (False, "Informazioni diagnostiche"),
    "idevicedate": (False, "Data e ora del dispositivo"),
    "ideviceprovision": (False, "Profili di provisioning"),
    "ideviceactivation": (False, "Stato di attivazione"),
    "ifuse": (False, "Mount AFC del filesystem media"),
    "ffmpeg": (False, "Assemblaggio dei frame in video"),
}

#: Estensioni usate per categorizzare i media estratti.
MEDIA_CATEGORIES: dict[str, tuple[str, ...]] = {
    "images": (".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif", ".tiff", ".bmp", ".webp"),
    "videos": (".mov", ".mp4", ".m4v", ".avi", ".3gp", ".mkv"),
    "audio": (".m4a", ".mp3", ".wav", ".aac", ".caf", ".aiff", ".amr"),
    "documents": (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf"),
    "databases": (".db", ".sqlite", ".sqlite3", ".sqlitedb"),
    "plists": (".plist",),
}

#: Categoria di appartenenza per estensione.
EXTENSION_CATEGORY: dict[str, str] = {
    extension: category
    for category, extensions in MEDIA_CATEGORIES.items()
    for extension in extensions
}

#: Timeout predefinito per i comandi esterni non interattivi (secondi).
DEFAULT_TIMEOUT = 120

#: Timeout per le operazioni lunghe, come il backup completo (secondi).
LONG_TIMEOUT = 7200

#: Nomi dei file di controllo di un backup iOS.
BACKUP_MARKERS = ("Manifest.db", "Manifest.plist", "Info.plist", "Status.plist")
