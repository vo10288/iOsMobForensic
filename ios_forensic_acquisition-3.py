#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════╗
║           iOS FORENSIC ACQUISITION TOOL v1.0                       ║
║           For Tsurugi Linux 2026 & macOS                           ║
║                                                                     ║
║  Mobile Forensic Acquisition Suite - iOS Edition                    ║
║  Uses libimobiledevice & pymobiledevice3                           ║
║                                                                     ║
║  Features:                                                          ║
║   - Full/Encrypted Backup Acquisition                              ║
║   - Device Information Extraction                                   ║
║   - Installed Applications List                                     ║
║   - Screenshot Acquisition                                          ║
║   - Screen Recording (sequential capture)                          ║
║   - System Log Capture                                              ║
║   - Crash Report Extraction                                         ║
║   - SHA-256 / MD5 Hash Verification                                ║
║   - Forensic Report Generation (HTML + TXT)                        ║
╚══════════════════════════════════════════════════════════════════════╝

Author: Forensic Analyst
License: GPLv3
Platform: Tsurugi Linux 2026 / macOS
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import subprocess
import threading
import os
import sys
import json
import hashlib
import datetime
import platform
import shutil
import time
import re
import signal
from pathlib import Path


# ─────────────────────────────────────────────
#  COSTANTI E CONFIGURAZIONE
# ─────────────────────────────────────────────

APP_NAME = "iOS Forensic Acquisition Tool"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Tsurugi Linux Forensic Suite"

COLORS = {
    "bg_dark": "#1a1a2e",
    "bg_medium": "#16213e",
    "bg_light": "#0f3460",
    "accent": "#e94560",
    "accent2": "#533483",
    "text": "#eaeaea",
    "text_dim": "#a0a0b0",
    "success": "#00c853",
    "warning": "#ffd600",
    "error": "#ff1744",
    "border": "#2a2a4a",
}

# Tool binaries - cercati nel PATH
IDEVICE_TOOLS = {
    "idevice_id": "idevice_id",
    "ideviceinfo": "ideviceinfo",
    "idevicename": "idevicename",
    "idevicebackup2": "idevicebackup2",
    "idevicescreenshot": "idevicescreenshot",
    "ideviceinstaller": "ideviceinstaller",
    "idevicesyslog": "idevicesyslog",
    "idevicecrashreport": "idevicecrashreport",
    "idevicepair": "idevicepair",
    "idevicediagnostics": "idevicediagnostics",
    "idevicedate": "idevicedate",
    "ideviceprovision": "ideviceprovision",
    "ideviceactivation": "ideviceactivation",
    "idevicenotificationproxy": "idevicenotificationproxy",
    "idevicesetlocation": "idevicesetlocation",
}

# Tool AFC per accesso file
AFC_TOOLS = {
    "ifuse": "ifuse",
    "idevicebackup": "idevicebackup",
}

# Estensioni media riconosciute
MEDIA_EXTENSIONS = {
    "images": {".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif", ".tiff", ".bmp", ".webp"},
    "videos": {".mov", ".mp4", ".m4v", ".avi", ".3gp"},
    "audio": {".m4a", ".mp3", ".wav", ".aac", ".caf", ".aiff"},
    "documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf"},
    "databases": {".db", ".sqlite", ".sqlite3", ".sqlitedb"},
    "plists": {".plist"},
}


# ─────────────────────────────────────────────
#  UTILITY FUNCTIONS
# ─────────────────────────────────────────────

def get_timestamp():
    """Ritorna timestamp formattato per nomi file."""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def get_timestamp_full():
    """Ritorna timestamp completo per log."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def calculate_hash(filepath, algorithms=None):
    """Calcola hash di un file con algoritmi multipli."""
    if algorithms is None:
        algorithms = ["md5", "sha1", "sha256"]
    
    hashes = {}
    hash_objects = {}
    
    for algo in algorithms:
        hash_objects[algo] = hashlib.new(algo)
    
    try:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                for algo in algorithms:
                    hash_objects[algo].update(chunk)
        
        for algo in algorithms:
            hashes[algo] = hash_objects[algo].hexdigest()
    except Exception as e:
        for algo in algorithms:
            hashes[algo] = f"ERRORE: {e}"
    
    return hashes


def calculate_dir_hashes(directory, algorithms=None):
    """Calcola hash per tutti i file in una directory."""
    if algorithms is None:
        algorithms = ["sha256"]
    
    results = []
    for root, dirs, files in os.walk(directory):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, directory)
            hashes = calculate_hash(fpath, algorithms)
            results.append({"file": rel_path, "hashes": hashes, "size": os.path.getsize(fpath)})
    return results


def check_tool_available(tool_name):
    """Verifica se un tool è disponibile nel PATH."""
    return shutil.which(tool_name) is not None


def run_command(cmd, timeout=None, capture_stderr=True):
    """Esegue un comando e ritorna output, stderr, returncode."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT: comando scaduto", -1
    except FileNotFoundError:
        return "", f"Tool non trovato: {cmd[0]}", -2
    except Exception as e:
        return "", f"Errore esecuzione: {e}", -3


def get_platform_info():
    """Rileva piattaforma e info sistema."""
    info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "node": platform.node(),
        "is_mac": platform.system() == "Darwin",
        "is_linux": platform.system() == "Linux",
        "is_tsurugi": False,
    }
    # Controlla se siamo su Tsurugi Linux
    if info["is_linux"]:
        try:
            with open("/etc/os-release", "r") as f:
                content = f.read().lower()
                if "tsurugi" in content:
                    info["is_tsurugi"] = True
        except:
            pass
    return info


# ─────────────────────────────────────────────
#  iOS DEVICE INTERFACE
# ─────────────────────────────────────────────

class iOSDeviceInterface:
    """Interfaccia per comunicare con dispositivi iOS via libimobiledevice."""
    
    def __init__(self, logger=None):
        self.logger = logger
        self.udid = None
        self.device_info = {}
        self.available_tools = {}
        self._check_tools()
    
    def log(self, msg, level="INFO"):
        if self.logger:
            self.logger(f"[{level}] {msg}")
    
    def _check_tools(self):
        """Verifica quali tool libimobiledevice sono disponibili."""
        for name, binary in IDEVICE_TOOLS.items():
            self.available_tools[name] = check_tool_available(binary)
        
        available = [k for k, v in self.available_tools.items() if v]
        missing = [k for k, v in self.available_tools.items() if not v]
        
        self.log(f"Tool disponibili: {', '.join(available) if available else 'NESSUNO'}")
        if missing:
            self.log(f"Tool mancanti: {', '.join(missing)}", "WARNING")
    
    def detect_device(self):
        """Rileva dispositivo iOS connesso."""
        if not self.available_tools.get("idevice_id"):
            return False, "idevice_id non disponibile. Installa libimobiledevice."
        
        stdout, stderr, rc = run_command(["idevice_id", "-l"], timeout=10)
        
        if rc != 0:
            return False, f"Errore rilevamento dispositivo: {stderr}"
        
        udids = [line.strip() for line in stdout.strip().split("\n") if line.strip()]
        
        if not udids:
            return False, "Nessun dispositivo iOS rilevato. Verifica connessione USB e trust."
        
        self.udid = udids[0]
        self.log(f"Dispositivo rilevato - UDID: {self.udid}")
        
        if len(udids) > 1:
            self.log(f"ATTENZIONE: {len(udids)} dispositivi rilevati. Uso il primo.", "WARNING")
        
        return True, self.udid
    
    def pair_device(self):
        """Effettua pairing con il dispositivo."""
        if not self.available_tools.get("idevicepair"):
            return False, "idevicepair non disponibile"
        
        stdout, stderr, rc = run_command(
            ["idevicepair", "-u", self.udid, "pair"] if self.udid else ["idevicepair", "pair"],
            timeout=30
        )
        
        if rc == 0:
            self.log("Pairing completato con successo")
            return True, stdout.strip()
        else:
            return False, f"Errore pairing: {stderr}"
    
    def validate_pair(self):
        """Valida il pairing esistente."""
        if not self.available_tools.get("idevicepair"):
            return False, "idevicepair non disponibile"
        
        cmd = ["idevicepair"]
        if self.udid:
            cmd.extend(["-u", self.udid])
        cmd.append("validate")
        
        stdout, stderr, rc = run_command(cmd, timeout=10)
        
        if rc == 0:
            self.log("Pairing validato")
            return True, "Pairing valido"
        else:
            return False, f"Pairing non valido: {stderr}"
    
    def get_device_info(self, domain=None):
        """Recupera informazioni dal dispositivo."""
        if not self.available_tools.get("ideviceinfo"):
            return False, "ideviceinfo non disponibile"
        
        cmd = ["ideviceinfo"]
        if self.udid:
            cmd.extend(["-u", self.udid])
        if domain:
            cmd.extend(["-q", domain])
        
        stdout, stderr, rc = run_command(cmd, timeout=15)
        
        if rc == 0:
            # Parse output key: value
            info = {}
            for line in stdout.split("\n"):
                if ": " in line:
                    key, _, value = line.partition(": ")
                    info[key.strip()] = value.strip()
            
            if not domain:
                self.device_info = info
            return True, info
        else:
            return False, f"Errore lettura info: {stderr}"
    
    def get_device_name(self):
        """Recupera il nome del dispositivo."""
        if not self.available_tools.get("idevicename"):
            return "Sconosciuto"
        
        cmd = ["idevicename"]
        if self.udid:
            cmd.extend(["-u", self.udid])
        
        stdout, stderr, rc = run_command(cmd, timeout=10)
        return stdout.strip() if rc == 0 else "Sconosciuto"
    
    def get_installed_apps(self, app_type="user"):
        """Lista applicazioni installate."""
        if not self.available_tools.get("ideviceinstaller"):
            return False, "ideviceinstaller non disponibile"
        
        cmd = ["ideviceinstaller"]
        if self.udid:
            cmd.extend(["-u", self.udid])
        
        if app_type == "all":
            cmd.extend(["-l", "-o", "list_all"])
        elif app_type == "system":
            cmd.extend(["-l", "-o", "list_system"])
        else:
            cmd.extend(["-l", "-o", "list_user"])
        
        stdout, stderr, rc = run_command(cmd, timeout=30)
        
        if rc == 0:
            apps = []
            for line in stdout.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("Total:") and " - " in line:
                    parts = line.split(" - ", 1)
                    bundle_id = parts[0].strip()
                    name_version = parts[1].strip() if len(parts) > 1 else ""
                    apps.append({"bundle_id": bundle_id, "name_version": name_version})
                elif line and not line.startswith("Total:") and ", " in line:
                    # Formato alternativo
                    apps.append({"bundle_id": line, "name_version": ""})
            return True, apps
        else:
            return False, f"Errore lista app: {stderr}"
    
    def take_screenshot(self, output_path):
        """Cattura screenshot del dispositivo."""
        if not self.available_tools.get("idevicescreenshot"):
            return False, "idevicescreenshot non disponibile"
        
        cmd = ["idevicescreenshot"]
        if self.udid:
            cmd.extend(["-u", self.udid])
        cmd.append(output_path)
        
        stdout, stderr, rc = run_command(cmd, timeout=15)
        
        if rc == 0 and os.path.exists(output_path):
            size = os.path.getsize(output_path)
            self.log(f"Screenshot salvato: {output_path} ({size} bytes)")
            return True, output_path
        else:
            return False, f"Errore screenshot: {stderr}"
    
    def start_backup(self, output_dir, encrypted=False, password=None, full=True,
                     progress_callback=None):
        """Avvia backup del dispositivo."""
        if not self.available_tools.get("idevicebackup2"):
            return False, "idevicebackup2 non disponibile"
        
        os.makedirs(output_dir, exist_ok=True)
        
        cmd = ["idevicebackup2"]
        if self.udid:
            cmd.extend(["-u", self.udid])
        
        if encrypted and password:
            # Abilita encryption
            enc_cmd = ["idevicebackup2"]
            if self.udid:
                enc_cmd.extend(["-u", self.udid])
            enc_cmd.extend(["encryption", "on", password])
            run_command(enc_cmd, timeout=15)
        
        cmd.append("backup")
        
        if full:
            cmd.append("--full")
        
        cmd.append(output_dir)
        
        self.log(f"Avvio backup in: {output_dir}")
        self.log(f"Comando: {' '.join(cmd)}")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            
            output_lines = []
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    line = line.strip()
                    output_lines.append(line)
                    if progress_callback:
                        progress_callback(line)
                    self.log(f"Backup: {line}")
            
            stderr = process.stderr.read()
            rc = process.returncode
            
            if rc == 0:
                self.log("Backup completato con successo!")
                return True, "\n".join(output_lines)
            else:
                return False, f"Errore backup (rc={rc}): {stderr}"
        
        except Exception as e:
            return False, f"Eccezione durante backup: {e}"
    
    def capture_syslog(self, output_path, duration=30, process_filter=None):
        """Cattura system log per una durata specificata."""
        if not self.available_tools.get("idevicesyslog"):
            return False, "idevicesyslog non disponibile"
        
        cmd = ["idevicesyslog"]
        if self.udid:
            cmd.extend(["-u", self.udid])
        if process_filter:
            cmd.extend(["-m", process_filter])
        
        self.log(f"Cattura syslog per {duration} secondi...")
        
        try:
            with open(output_path, "w") as outfile:
                process = subprocess.Popen(
                    cmd,
                    stdout=outfile,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                
                time.sleep(duration)
                process.send_signal(signal.SIGTERM)
                
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            
            if os.path.exists(output_path):
                size = os.path.getsize(output_path)
                self.log(f"Syslog catturato: {output_path} ({size} bytes)")
                return True, output_path
            else:
                return False, "File syslog non creato"
        
        except Exception as e:
            return False, f"Errore cattura syslog: {e}"
    
    def extract_crash_reports(self, output_dir):
        """Estrae crash reports dal dispositivo."""
        if not self.available_tools.get("idevicecrashreport"):
            return False, "idevicecrashreport non disponibile"
        
        os.makedirs(output_dir, exist_ok=True)
        
        cmd = ["idevicecrashreport"]
        if self.udid:
            cmd.extend(["-u", self.udid])
        cmd.extend(["-e", output_dir])  # -e = extract
        
        stdout, stderr, rc = run_command(cmd, timeout=120)
        
        if rc == 0:
            count = sum(1 for _ in Path(output_dir).rglob("*") if _.is_file())
            self.log(f"Crash reports estratti: {count} file in {output_dir}")
            return True, f"{count} crash reports estratti"
        else:
            return False, f"Errore crash reports: {stderr}"
    
    def get_device_date(self):
        """Recupera data/ora del dispositivo."""
        if not self.available_tools.get("idevicedate"):
            return None
        
        cmd = ["idevicedate"]
        if self.udid:
            cmd.extend(["-u", self.udid])
        
        stdout, stderr, rc = run_command(cmd, timeout=10)
        return stdout.strip() if rc == 0 else None
    
    def get_diagnostics(self, diag_type="All"):
        """Recupera info diagnostiche."""
        if not self.available_tools.get("idevicediagnostics"):
            return False, "idevicediagnostics non disponibile"
        
        cmd = ["idevicediagnostics", "diagnostics", diag_type]
        if self.udid:
            cmd.extend(["-u", self.udid])
        
        stdout, stderr, rc = run_command(cmd, timeout=15)
        
        if rc == 0:
            return True, stdout
        else:
            return False, f"Errore diagnostica: {stderr}"
    
    def get_provisioning_profiles(self, output_dir):
        """Estrae provisioning profiles dal dispositivo."""
        if not self.available_tools.get("ideviceprovision"):
            return False, "ideviceprovision non disponibile"
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Prima lista
        cmd = ["ideviceprovision"]
        if self.udid:
            cmd.extend(["-u", self.udid])
        cmd.append("list")
        
        stdout, stderr, rc = run_command(cmd, timeout=15)
        
        list_result = stdout if rc == 0 else f"Errore lista: {stderr}"
        
        # Poi copia i profili
        cmd_copy = ["ideviceprovision"]
        if self.udid:
            cmd_copy.extend(["-u", self.udid])
        cmd_copy.extend(["copy", output_dir])
        
        stdout2, stderr2, rc2 = run_command(cmd_copy, timeout=30)
        
        if rc2 == 0:
            count = sum(1 for f in os.listdir(output_dir) if f.endswith('.mobileprovision'))
            self.log(f"Provisioning profiles estratti: {count}")
            return True, {"list": list_result, "count": count}
        else:
            # Salva almeno la lista
            return rc == 0, {"list": list_result, "count": 0, "error": stderr2}
    
    def get_activation_info(self):
        """Recupera info di attivazione."""
        if not self.available_tools.get("ideviceactivation"):
            return False, "ideviceactivation non disponibile"
        
        cmd = ["ideviceactivation", "state"]
        if self.udid:
            cmd.extend(["-u", self.udid])
        
        stdout, stderr, rc = run_command(cmd, timeout=15)
        
        if rc == 0:
            return True, stdout.strip()
        else:
            return False, f"Errore: {stderr}"
    
    def mount_afc(self, mount_point):
        """Monta il filesystem AFC via ifuse."""
        if not check_tool_available("ifuse"):
            return False, "ifuse non installato. Installa con: apt install ifuse (Linux) o brew install ifuse (macOS)"
        
        os.makedirs(mount_point, exist_ok=True)
        
        cmd = ["ifuse"]
        if self.udid:
            cmd.extend(["-u", self.udid])
        cmd.append(mount_point)
        
        stdout, stderr, rc = run_command(cmd, timeout=15)
        
        if rc == 0:
            self.log(f"AFC montato in: {mount_point}")
            return True, mount_point
        else:
            return False, f"Errore mount AFC: {stderr}"
    
    def mount_afc_app(self, mount_point, bundle_id):
        """Monta i documenti di una app specifica via AFC."""
        if not check_tool_available("ifuse"):
            return False, "ifuse non installato"
        
        os.makedirs(mount_point, exist_ok=True)
        
        cmd = ["ifuse", "--documents", bundle_id]
        if self.udid:
            cmd.extend(["-u", self.udid])
        cmd.append(mount_point)
        
        stdout, stderr, rc = run_command(cmd, timeout=15)
        
        if rc == 0:
            self.log(f"AFC App ({bundle_id}) montato in: {mount_point}")
            return True, mount_point
        else:
            return False, f"Errore mount AFC app: {stderr}"
    
    def unmount_afc(self, mount_point):
        """Smonta filesystem AFC."""
        # Su macOS: umount, su Linux: fusermount -u
        if platform.system() == "Darwin":
            cmd = ["umount", mount_point]
        else:
            cmd = ["fusermount", "-u", mount_point]
        
        stdout, stderr, rc = run_command(cmd, timeout=10)
        
        if rc == 0:
            self.log(f"AFC smontato: {mount_point}")
            return True, "Smontato"
        else:
            return False, f"Errore unmount: {stderr}"
    
    def list_afc_files(self, mount_point, max_depth=3):
        """Lista file dal mount AFC."""
        files = []
        try:
            for root, dirs, fnames in os.walk(mount_point):
                depth = root.replace(mount_point, '').count(os.sep)
                if depth >= max_depth:
                    dirs.clear()
                    continue
                for fname in fnames:
                    fpath = os.path.join(root, fname)
                    rel_path = os.path.relpath(fpath, mount_point)
                    try:
                        size = os.path.getsize(fpath)
                        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
                    except OSError:
                        size = 0
                        mtime = None
                    
                    _, ext = os.path.splitext(fname.lower())
                    file_type = "other"
                    for category, extensions in MEDIA_EXTENSIONS.items():
                        if ext in extensions:
                            file_type = category
                            break
                    
                    files.append({
                        "path": rel_path,
                        "size": size,
                        "mtime": mtime.isoformat() if mtime else "N/A",
                        "type": file_type,
                        "ext": ext,
                    })
        except Exception as e:
            self.log(f"Errore scansione AFC: {e}", "ERROR")
        
        return files
    
    def copy_afc_files(self, mount_point, dest_dir, file_types=None):
        """Copia file dal mount AFC a destinazione, filtrabili per tipo."""
        os.makedirs(dest_dir, exist_ok=True)
        copied = 0
        errors = 0
        
        for root, dirs, fnames in os.walk(mount_point):
            for fname in fnames:
                _, ext = os.path.splitext(fname.lower())
                
                if file_types:
                    match = False
                    for ft in file_types:
                        if ext in MEDIA_EXTENSIONS.get(ft, set()):
                            match = True
                            break
                    if not match:
                        continue
                
                src = os.path.join(root, fname)
                rel = os.path.relpath(src, mount_point)
                dst = os.path.join(dest_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                
                try:
                    shutil.copy2(src, dst)
                    copied += 1
                except Exception as e:
                    self.log(f"Errore copia {rel}: {e}", "ERROR")
                    errors += 1
        
        self.log(f"AFC copy: {copied} file copiati, {errors} errori")
        return copied, errors


# ─────────────────────────────────────────────
#  SYSLOG PROCESS PARSER
# ─────────────────────────────────────────────

class SyslogProcessParser:
    """Analizza output syslog per estrarre processi attivi e attività."""
    
    # Pattern comuni nel syslog iOS
    PROCESS_PATTERN = re.compile(
        r'\w+\s+\d+\s+[\d:]+\s+\S+\s+(\S+)\[(\d+)\]'
    )
    
    SUBSYSTEM_PATTERN = re.compile(
        r'(\S+)\((\S+)\)\[(\d+)\]'
    )
    
    @staticmethod
    def parse_syslog_file(filepath):
        """Analizza un file syslog e estrae processi unici."""
        processes = {}
        activity_timeline = []
        line_count = 0
        
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line_count += 1
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Cerca processo nel formato standard syslog
                    match = SyslogProcessParser.PROCESS_PATTERN.search(line)
                    if match:
                        proc_name = match.group(1)
                        pid = match.group(2)
                        
                        if proc_name not in processes:
                            processes[proc_name] = {
                                "name": proc_name,
                                "pids": set(),
                                "first_seen": line_count,
                                "last_seen": line_count,
                                "count": 0,
                            }
                        
                        processes[proc_name]["pids"].add(pid)
                        processes[proc_name]["last_seen"] = line_count
                        processes[proc_name]["count"] += 1
                    
                    # Cerca pattern subsystem
                    match2 = SyslogProcessParser.SUBSYSTEM_PATTERN.search(line)
                    if match2:
                        proc_name = match2.group(1)
                        subsystem = match2.group(2)
                        pid = match2.group(3)
                        
                        if proc_name not in processes:
                            processes[proc_name] = {
                                "name": proc_name,
                                "pids": set(),
                                "first_seen": line_count,
                                "last_seen": line_count,
                                "count": 0,
                            }
                        
                        processes[proc_name]["pids"].add(pid)
                        processes[proc_name]["last_seen"] = line_count
                        processes[proc_name]["count"] += 1
        
        except Exception as e:
            return {"error": str(e), "processes": {}, "total_lines": line_count}
        
        # Converti set di PID in liste per serializzazione
        for proc in processes.values():
            proc["pids"] = sorted(list(proc["pids"]))
        
        return {
            "processes": processes,
            "total_lines": line_count,
            "unique_processes": len(processes),
        }
    
    @staticmethod
    def generate_process_report(parse_result, output_path):
        """Genera report testuale dei processi trovati."""
        lines = []
        sep = "=" * 65
        
        lines.append(sep)
        lines.append("  REPORT PROCESSI iOS (estratti da syslog)")
        lines.append(sep)
        lines.append("")
        lines.append(f"  Righe syslog analizzate: {parse_result['total_lines']}")
        lines.append(f"  Processi unici trovati:  {parse_result['unique_processes']}")
        lines.append("")
        lines.append("-" * 65)
        lines.append(f"  {'PROCESSO':<35} {'PID(s)':<15} {'MESSAGGI':>8}")
        lines.append("-" * 65)
        
        # Ordina per numero messaggi (più attivi prima)
        sorted_procs = sorted(
            parse_result["processes"].values(),
            key=lambda x: x["count"],
            reverse=True
        )
        
        for proc in sorted_procs:
            pids_str = ",".join(proc["pids"][:5])
            if len(proc["pids"]) > 5:
                pids_str += f"+{len(proc['pids'])-5}"
            lines.append(f"  {proc['name']:<35} {pids_str:<15} {proc['count']:>8}")
        
        lines.append("")
        lines.append(sep)
        lines.append(f"  Report generato: {get_timestamp_full()}")
        lines.append(sep)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        return output_path


# ─────────────────────────────────────────────
#  BACKUP ANALYZER
# ─────────────────────────────────────────────

class BackupAnalyzer:
    """Analizza struttura di un backup iOS."""
    
    @staticmethod
    def analyze_backup_dir(backup_dir):
        """Analizza la directory di backup e categorizza i file."""
        stats = {
            "total_files": 0,
            "total_size": 0,
            "by_extension": {},
            "by_type": {cat: {"count": 0, "size": 0} for cat in MEDIA_EXTENSIONS},
            "manifest_found": False,
            "info_plist_found": False,
            "status_plist_found": False,
            "largest_files": [],
        }
        
        all_files = []
        
        for root, dirs, files in os.walk(backup_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    size = os.path.getsize(fpath)
                except OSError:
                    size = 0
                
                stats["total_files"] += 1
                stats["total_size"] += size
                
                _, ext = os.path.splitext(fname.lower())
                if ext:
                    stats["by_extension"][ext] = stats["by_extension"].get(ext, 0) + 1
                
                # Categorizza
                for category, extensions in MEDIA_EXTENSIONS.items():
                    if ext in extensions:
                        stats["by_type"][category]["count"] += 1
                        stats["by_type"][category]["size"] += size
                
                # File speciali backup
                if fname == "Manifest.db":
                    stats["manifest_found"] = True
                elif fname == "Manifest.plist":
                    stats["manifest_found"] = True
                elif fname == "Info.plist":
                    stats["info_plist_found"] = True
                elif fname == "Status.plist":
                    stats["status_plist_found"] = True
                
                all_files.append((os.path.relpath(fpath, backup_dir), size))
        
        # Top 20 file più grandi
        all_files.sort(key=lambda x: x[1], reverse=True)
        stats["largest_files"] = all_files[:20]
        
        return stats
    
    @staticmethod
    def find_media_in_backup(backup_dir, media_types=None):
        """Trova file media nel backup."""
        if media_types is None:
            media_types = ["images", "videos", "audio"]
        
        target_exts = set()
        for mt in media_types:
            target_exts.update(MEDIA_EXTENSIONS.get(mt, set()))
        
        found = []
        for root, dirs, files in os.walk(backup_dir):
            for fname in files:
                _, ext = os.path.splitext(fname.lower())
                if ext in target_exts:
                    fpath = os.path.join(root, fname)
                    try:
                        size = os.path.getsize(fpath)
                    except OSError:
                        size = 0
                    found.append({
                        "path": os.path.relpath(fpath, backup_dir),
                        "full_path": fpath,
                        "size": size,
                        "ext": ext,
                    })
        
        return found
    
    @staticmethod
    def extract_media_from_backup(backup_dir, output_dir, media_types=None):
        """Estrae e copia file media dal backup in una directory organizzata."""
        found = BackupAnalyzer.find_media_in_backup(backup_dir, media_types)
        os.makedirs(output_dir, exist_ok=True)
        
        # Crea sottodirectory per tipo
        for cat in MEDIA_EXTENSIONS:
            os.makedirs(os.path.join(output_dir, cat), exist_ok=True)
        
        copied = 0
        for item in found:
            for category, extensions in MEDIA_EXTENSIONS.items():
                if item["ext"] in extensions:
                    dst = os.path.join(output_dir, category, os.path.basename(item["path"]))
                    # Evita sovrascritture
                    if os.path.exists(dst):
                        base, ext = os.path.splitext(dst)
                        dst = f"{base}_{copied}{ext}"
                    try:
                        shutil.copy2(item["full_path"], dst)
                        copied += 1
                    except Exception:
                        pass
                    break
        
        return copied, len(found)


# ─────────────────────────────────────────────
#  INTEGRITY VERIFIER
# ─────────────────────────────────────────────

class IntegrityVerifier:
    """Verifica l'integrità dei file acquisiti tramite hash."""
    
    @staticmethod
    def create_hash_manifest(directory, output_path, algorithms=None):
        """Crea un manifest di hash per tutti i file in una directory."""
        if algorithms is None:
            algorithms = ["sha256"]
        
        entries = []
        for root, dirs, files in os.walk(directory):
            for fname in sorted(files):
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, directory)
                
                hashes = calculate_hash(fpath, algorithms)
                size = os.path.getsize(fpath)
                
                entries.append({
                    "file": rel_path,
                    "size": size,
                    "hashes": hashes,
                })
        
        # Salva manifest in formato testo
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# Hash Manifest - {get_timestamp_full()}\n")
            f.write(f"# Directory: {directory}\n")
            f.write(f"# Algoritmi: {', '.join(algorithms)}\n")
            f.write(f"# File totali: {len(entries)}\n\n")
            
            for entry in entries:
                for algo in algorithms:
                    f.write(f"{entry['hashes'][algo]}  {entry['file']}  ({entry['size']} bytes)\n")
        
        # Salva anche in JSON
        json_path = output_path.replace(".txt", ".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": get_timestamp_full(),
                "directory": directory,
                "algorithms": algorithms,
                "entries": entries,
            }, f, indent=2, ensure_ascii=False)
        
        return len(entries), output_path, json_path
    
    @staticmethod
    def verify_hash_manifest(manifest_json_path):
        """Verifica l'integrità dei file rispetto a un manifest JSON."""
        try:
            with open(manifest_json_path, "r") as f:
                manifest = json.load(f)
        except Exception as e:
            return False, f"Errore lettura manifest: {e}", []
        
        base_dir = manifest.get("directory", "")
        algorithms = manifest.get("algorithms", ["sha256"])
        entries = manifest.get("entries", [])
        
        results = []
        passed = 0
        failed = 0
        missing = 0
        
        for entry in entries:
            fpath = os.path.join(base_dir, entry["file"])
            
            if not os.path.exists(fpath):
                results.append({
                    "file": entry["file"],
                    "status": "MANCANTE",
                    "expected": entry["hashes"],
                    "actual": {},
                })
                missing += 1
                continue
            
            current_hashes = calculate_hash(fpath, algorithms)
            match = all(
                entry["hashes"].get(algo) == current_hashes.get(algo)
                for algo in algorithms
            )
            
            if match:
                results.append({
                    "file": entry["file"],
                    "status": "OK",
                    "expected": entry["hashes"],
                    "actual": current_hashes,
                })
                passed += 1
            else:
                results.append({
                    "file": entry["file"],
                    "status": "ALTERATO",
                    "expected": entry["hashes"],
                    "actual": current_hashes,
                })
                failed += 1
        
        summary = {
            "total": len(entries),
            "passed": passed,
            "failed": failed,
            "missing": missing,
            "integrity": "OK" if failed == 0 and missing == 0 else "COMPROMESSA",
        }
        
        return summary["integrity"] == "OK", summary, results


# ─────────────────────────────────────────────
#  SCREEN RECORDER (Sequential Screenshots)
# ─────────────────────────────────────────────

class ScreenRecorder:
    """Registrazione schermo tramite screenshot sequenziali."""
    
    def __init__(self, device_interface, output_dir, interval=0.5, logger=None):
        self.device = device_interface
        self.output_dir = output_dir
        self.interval = interval
        self.logger = logger
        self.recording = False
        self.frame_count = 0
        self._thread = None
    
    def log(self, msg):
        if self.logger:
            self.logger(f"[RECORDER] {msg}")
    
    def start(self):
        """Avvia la registrazione."""
        if self.recording:
            return
        
        os.makedirs(self.output_dir, exist_ok=True)
        self.recording = True
        self.frame_count = 0
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()
        self.log("Registrazione avviata")
    
    def stop(self):
        """Ferma la registrazione."""
        self.recording = False
        if self._thread:
            self._thread.join(timeout=5)
        self.log(f"Registrazione fermata. Frame catturati: {self.frame_count}")
        return self.frame_count
    
    def _record_loop(self):
        """Loop di cattura screenshot."""
        while self.recording:
            self.frame_count += 1
            fname = f"frame_{self.frame_count:06d}.png"
            fpath = os.path.join(self.output_dir, fname)
            
            success, _ = self.device.take_screenshot(fpath)
            
            if not success:
                self.log(f"Errore cattura frame {self.frame_count}")
                # Breve pausa e riprova
                time.sleep(1)
                continue
            
            time.sleep(self.interval)
    
    def create_video(self, output_path=None, fps=2):
        """Crea video dai frame catturati (richiede ffmpeg)."""
        if not check_tool_available("ffmpeg"):
            self.log("ffmpeg non disponibile - impossibile creare video")
            return False, "ffmpeg non installato"
        
        if output_path is None:
            output_path = os.path.join(os.path.dirname(self.output_dir), "screen_recording.mp4")
        
        pattern = os.path.join(self.output_dir, "frame_%06d.png")
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", pattern,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "18",
            output_path
        ]
        
        stdout, stderr, rc = run_command(cmd, timeout=300)
        
        if rc == 0 and os.path.exists(output_path):
            self.log(f"Video creato: {output_path}")
            return True, output_path
        else:
            return False, f"Errore creazione video: {stderr}"


# ─────────────────────────────────────────────
#  FORENSIC REPORT GENERATOR
# ─────────────────────────────────────────────

class ForensicReportGenerator:
    """Genera report forensi in HTML e TXT."""
    
    def __init__(self, case_info, examiner_info, device_info, acquisition_log):
        self.case_info = case_info
        self.examiner_info = examiner_info
        self.device_info = device_info
        self.acquisition_log = acquisition_log
        self.artifacts = []
    
    def add_artifact(self, name, path, hashes, description=""):
        """Aggiunge un artefatto al report."""
        self.artifacts.append({
            "name": name,
            "path": path,
            "hashes": hashes,
            "description": description,
            "timestamp": get_timestamp_full(),
        })
    
    def generate_txt(self, output_path):
        """Genera report in formato TXT."""
        lines = []
        sep = "=" * 72
        
        lines.append(sep)
        lines.append("  REPORT DI ACQUISIZIONE FORENSE - iOS")
        lines.append(f"  {APP_NAME} v{APP_VERSION}")
        lines.append(sep)
        lines.append("")
        
        # Info caso
        lines.append("INFORMAZIONI CASO")
        lines.append("-" * 40)
        for k, v in self.case_info.items():
            lines.append(f"  {k}: {v}")
        lines.append("")
        
        # Info esaminatore
        lines.append("INFORMAZIONI ESAMINATORE")
        lines.append("-" * 40)
        for k, v in self.examiner_info.items():
            lines.append(f"  {k}: {v}")
        lines.append("")
        
        # Info dispositivo
        lines.append("INFORMAZIONI DISPOSITIVO")
        lines.append("-" * 40)
        for k, v in self.device_info.items():
            lines.append(f"  {k}: {v}")
        lines.append("")
        
        # Piattaforma
        lines.append("INFORMAZIONI PIATTAFORMA")
        lines.append("-" * 40)
        pinfo = get_platform_info()
        for k, v in pinfo.items():
            lines.append(f"  {k}: {v}")
        lines.append("")
        
        # Artefatti acquisiti
        lines.append("ARTEFATTI ACQUISITI")
        lines.append("-" * 40)
        for i, art in enumerate(self.artifacts, 1):
            lines.append(f"  [{i}] {art['name']}")
            lines.append(f"      Percorso: {art['path']}")
            lines.append(f"      Timestamp: {art['timestamp']}")
            if art['description']:
                lines.append(f"      Descrizione: {art['description']}")
            for algo, h in art['hashes'].items():
                lines.append(f"      {algo.upper()}: {h}")
            lines.append("")
        
        # Log acquisizione
        lines.append("LOG ACQUISIZIONE")
        lines.append("-" * 40)
        for entry in self.acquisition_log:
            lines.append(f"  {entry}")
        lines.append("")
        
        lines.append(sep)
        lines.append(f"  Report generato il: {get_timestamp_full()}")
        lines.append(f"  Tool: {APP_NAME} v{APP_VERSION}")
        lines.append(sep)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        return output_path
    
    def generate_html(self, output_path):
        """Genera report in formato HTML."""
        html = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Report Acquisizione Forense iOS - {self.case_info.get('Numero Caso', 'N/A')}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 900px; margin: 0 auto; padding: 20px;
            background: #f5f5f5; color: #333;
        }}
        .header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            color: white; padding: 30px; border-radius: 10px;
            margin-bottom: 20px; text-align: center;
        }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .header p {{ margin: 5px 0 0; opacity: 0.8; }}
        .section {{
            background: white; border-radius: 8px; padding: 20px;
            margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            color: #0f3460; border-bottom: 2px solid #e94560;
            padding-bottom: 8px; margin-top: 0;
        }}
        table {{ width: 100%; border-collapse: collapse; }}
        td, th {{
            padding: 8px 12px; text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{ background: #f8f9fa; font-weight: 600; width: 30%; }}
        .hash {{ font-family: monospace; font-size: 12px; color: #666; word-break: break-all; }}
        .artifact {{
            border-left: 4px solid #e94560; padding: 10px 15px;
            margin: 10px 0; background: #fafafa;
        }}
        .log {{
            background: #1a1a2e; color: #00ff00; padding: 15px;
            border-radius: 5px; font-family: monospace; font-size: 12px;
            max-height: 400px; overflow-y: auto; white-space: pre-wrap;
        }}
        .footer {{
            text-align: center; padding: 20px; color: #888; font-size: 12px;
        }}
        .badge {{
            display: inline-block; padding: 2px 8px; border-radius: 3px;
            font-size: 11px; font-weight: bold;
        }}
        .badge-success {{ background: #e8f5e9; color: #2e7d32; }}
        .badge-info {{ background: #e3f2fd; color: #1565c0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>&#128270; Report Acquisizione Forense - iOS</h1>
        <p>{APP_NAME} v{APP_VERSION}</p>
        <p>Generato il: {get_timestamp_full()}</p>
    </div>
    
    <div class="section">
        <h2>Informazioni Caso</h2>
        <table>
"""
        for k, v in self.case_info.items():
            html += f"            <tr><th>{k}</th><td>{v}</td></tr>\n"
        
        html += """        </table>
    </div>
    
    <div class="section">
        <h2>Informazioni Esaminatore</h2>
        <table>
"""
        for k, v in self.examiner_info.items():
            html += f"            <tr><th>{k}</th><td>{v}</td></tr>\n"
        
        html += """        </table>
    </div>
    
    <div class="section">
        <h2>Informazioni Dispositivo</h2>
        <table>
"""
        for k, v in self.device_info.items():
            html += f"            <tr><th>{k}</th><td>{v}</td></tr>\n"
        
        html += """        </table>
    </div>
    
    <div class="section">
        <h2>Artefatti Acquisiti</h2>
"""
        for i, art in enumerate(self.artifacts, 1):
            html += f"""        <div class="artifact">
            <strong>[{i}] {art['name']}</strong>
            <span class="badge badge-success">Acquisito</span><br>
            <small>Percorso: {art['path']}</small><br>
            <small>Timestamp: {art['timestamp']}</small><br>
"""
            if art['description']:
                html += f"            <small>Note: {art['description']}</small><br>\n"
            for algo, h in art['hashes'].items():
                html += f'            <small class="hash">{algo.upper()}: {h}</small><br>\n'
            html += "        </div>\n"
        
        html += """    </div>
    
    <div class="section">
        <h2>Log Acquisizione</h2>
        <div class="log">
"""
        for entry in self.acquisition_log:
            html += f"{entry}\n"
        
        html += f"""        </div>
    </div>
    
    <div class="section">
        <h2>Informazioni Piattaforma</h2>
        <table>
"""
        pinfo = get_platform_info()
        for k, v in pinfo.items():
            html += f"            <tr><th>{k}</th><td>{v}</td></tr>\n"
        
        html += """        </table>
    </div>
    
    <div class="footer">
        <p>Questo report è stato generato automaticamente da """ + APP_NAME + " v" + APP_VERSION + """</p>
        <p>I valori hash garantiscono l'integrità dei dati acquisiti.</p>
    </div>
</body>
</html>"""
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        
        return output_path


# ─────────────────────────────────────────────
#  MAIN GUI APPLICATION
# ─────────────────────────────────────────────

class iOSForensicApp:
    """Applicazione principale GUI."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1050x780")
        self.root.minsize(900, 650)
        
        # State — acquisition_log e _artifacts_list PRIMA di device
        # perché iOSDeviceInterface chiama log_message durante __init__
        self.acquisition_log = []
        self._artifacts_list = []
        self.log_text = None  # widget creato dopo in _build_gui
        
        self.output_base_dir = os.path.expanduser("~/iOS_Forensic_Acquisitions")
        self.current_case_dir = None
        self.screen_recorder = None
        self.is_recording = False
        self.platform_info = get_platform_info()
        self.device = iOSDeviceInterface(logger=self.log_message)
        
        # Variabili tkinter
        self.var_case_number = tk.StringVar()
        self.var_case_desc = tk.StringVar()
        self.var_examiner_name = tk.StringVar()
        self.var_examiner_org = tk.StringVar()
        self.var_examiner_note = tk.StringVar()
        self.var_device_status = tk.StringVar(value="Non connesso")
        self.var_backup_encrypted = tk.BooleanVar(value=False)
        self.var_backup_password = tk.StringVar()
        self.var_backup_full = tk.BooleanVar(value=True)
        self.var_syslog_duration = tk.IntVar(value=30)
        self.var_syslog_filter = tk.StringVar()
        self.var_record_interval = tk.DoubleVar(value=1.0)
        self.var_record_fps = tk.IntVar(value=2)
        
        self._setup_styles()
        self._build_gui()
        self._check_dependencies()
    
    def _setup_styles(self):
        """Configura stili ttk."""
        style = ttk.Style()
        style.theme_use("clam")
        
        style.configure("Title.TLabel", font=("Helvetica", 16, "bold"))
        style.configure("Subtitle.TLabel", font=("Helvetica", 11))
        style.configure("Status.TLabel", font=("Helvetica", 10))
        style.configure("Bold.TLabel", font=("Helvetica", 10, "bold"))
        
        style.configure("Accent.TButton", font=("Helvetica", 10, "bold"))
        style.configure("Danger.TButton", font=("Helvetica", 10, "bold"))
        
        style.configure("Header.TFrame", background="#16213e")
    
    def _build_gui(self):
        """Costruisce l'interfaccia grafica."""
        
        # ── Top Bar ──
        top_frame = tk.Frame(self.root, bg=COLORS["bg_dark"], height=70)
        top_frame.pack(fill="x")
        top_frame.pack_propagate(False)
        
        title_lbl = tk.Label(
            top_frame, text=f"📱 {APP_NAME}",
            font=("Helvetica", 18, "bold"),
            bg=COLORS["bg_dark"], fg=COLORS["text"]
        )
        title_lbl.pack(side="left", padx=15, pady=10)
        
        platform_text = "🐧 Tsurugi Linux" if self.platform_info["is_tsurugi"] else \
                        "🍎 macOS" if self.platform_info["is_mac"] else \
                        f"🐧 {self.platform_info['system']}"
        
        plat_lbl = tk.Label(
            top_frame, text=platform_text,
            font=("Helvetica", 10),
            bg=COLORS["bg_dark"], fg=COLORS["text_dim"]
        )
        plat_lbl.pack(side="right", padx=15)
        
        ver_lbl = tk.Label(
            top_frame, text=f"v{APP_VERSION}",
            font=("Helvetica", 10),
            bg=COLORS["bg_dark"], fg=COLORS["accent"]
        )
        ver_lbl.pack(side="right", padx=5)
        
        # ── Status Bar ──
        status_frame = tk.Frame(self.root, bg=COLORS["bg_medium"], height=35)
        status_frame.pack(fill="x")
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(
            status_frame, textvariable=self.var_device_status,
            font=("Helvetica", 10),
            bg=COLORS["bg_medium"], fg=COLORS["warning"]
        )
        self.status_label.pack(side="left", padx=15, pady=5)
        
        btn_detect = ttk.Button(status_frame, text="🔍 Rileva Dispositivo",
                                command=self.cmd_detect_device)
        btn_detect.pack(side="right", padx=5, pady=3)
        
        btn_pair = ttk.Button(status_frame, text="🔗 Pair",
                              command=self.cmd_pair_device)
        btn_pair.pack(side="right", padx=5, pady=3)
        
        # ── Main Content: Notebook ──
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Tab 1: Info Caso
        self._build_tab_case()
        # Tab 2: Device Info
        self._build_tab_device()
        # Tab 3: Backup
        self._build_tab_backup()
        # Tab 4: Screenshot & Recording
        self._build_tab_screenshot()
        # Tab 5: System Log & Crash
        self._build_tab_syslog()
        # Tab 6: App List
        self._build_tab_apps()
        # Tab 7: File & Media (AFC)
        self._build_tab_files()
        # Tab 8: Integrità
        self._build_tab_integrity()
        # Tab 9: Report
        self._build_tab_report()
        
        # ── Log Panel ──
        log_frame = ttk.LabelFrame(self.root, text=" Log Operazioni ")
        log_frame.pack(fill="x", padx=5, pady=(0, 5))
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=8,
            font=("Consolas", 9),
            bg="#0a0a15", fg="#00ff88",
            insertbackground="#00ff88",
            wrap="word"
        )
        self.log_text.pack(fill="x", padx=3, pady=3)
        
        # Replay messaggi di log accumulati prima della creazione del widget
        for early_msg in self.acquisition_log:
            self.log_text.insert("end", early_msg + "\n")
        
        # Log iniziale
        self.log_message(f"[START] {APP_NAME} v{APP_VERSION} avviato")
        self.log_message(f"[INFO] Piattaforma: {self.platform_info['system']} {self.platform_info['release']}")
        self.log_message(f"[INFO] Directory output: {self.output_base_dir}")
    
    def _build_tab_case(self):
        """Tab informazioni caso ed esaminatore."""
        frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(frame, text=" 📋 Caso ")
        
        # Caso
        lf_case = ttk.LabelFrame(frame, text=" Informazioni Caso ", padding=10)
        lf_case.pack(fill="x", pady=(0, 10))
        
        row = ttk.Frame(lf_case)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Numero Caso:", width=20, style="Bold.TLabel").pack(side="left")
        ttk.Entry(row, textvariable=self.var_case_number, width=40).pack(side="left", padx=5)
        
        row = ttk.Frame(lf_case)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Descrizione:", width=20, style="Bold.TLabel").pack(side="left")
        ttk.Entry(row, textvariable=self.var_case_desc, width=60).pack(side="left", padx=5, fill="x", expand=True)
        
        row = ttk.Frame(lf_case)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Directory Output:", width=20, style="Bold.TLabel").pack(side="left")
        self.var_output_dir = tk.StringVar(value=self.output_base_dir)
        ttk.Entry(row, textvariable=self.var_output_dir, width=50).pack(side="left", padx=5, fill="x", expand=True)
        ttk.Button(row, text="📁", width=3, command=self._browse_output_dir).pack(side="left")
        
        # Esaminatore
        lf_exam = ttk.LabelFrame(frame, text=" Informazioni Esaminatore ", padding=10)
        lf_exam.pack(fill="x", pady=(0, 10))
        
        row = ttk.Frame(lf_exam)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Nome Esaminatore:", width=20, style="Bold.TLabel").pack(side="left")
        ttk.Entry(row, textvariable=self.var_examiner_name, width=40).pack(side="left", padx=5)
        
        row = ttk.Frame(lf_exam)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Organizzazione:", width=20, style="Bold.TLabel").pack(side="left")
        ttk.Entry(row, textvariable=self.var_examiner_org, width=40).pack(side="left", padx=5)
        
        row = ttk.Frame(lf_exam)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Note:", width=20, style="Bold.TLabel").pack(side="left")
        ttk.Entry(row, textvariable=self.var_examiner_note, width=60).pack(side="left", padx=5, fill="x", expand=True)
        
        # Bottone inizializza caso
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=10)
        ttk.Button(btn_frame, text="✅ Inizializza Caso",
                   command=self.cmd_init_case, style="Accent.TButton").pack(pady=5)
    
    def _build_tab_device(self):
        """Tab informazioni dispositivo."""
        frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(frame, text=" 📱 Dispositivo ")
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Button(btn_frame, text="🔄 Aggiorna Info Dispositivo",
                   command=self.cmd_get_device_info).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="💾 Salva Info Dispositivo",
                   command=self.cmd_save_device_info).pack(side="left", padx=5)
        
        self.device_info_text = scrolledtext.ScrolledText(
            frame, height=25,
            font=("Consolas", 10),
            wrap="word"
        )
        self.device_info_text.pack(fill="both", expand=True)
    
    def _build_tab_backup(self):
        """Tab acquisizione backup."""
        frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(frame, text=" 💾 Backup ")
        
        # Opzioni
        lf_opts = ttk.LabelFrame(frame, text=" Opzioni Backup ", padding=10)
        lf_opts.pack(fill="x", pady=(0, 10))
        
        row = ttk.Frame(lf_opts)
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, text="Backup Completo (Full)",
                        variable=self.var_backup_full).pack(side="left")
        
        row = ttk.Frame(lf_opts)
        row.pack(fill="x", pady=2)
        ttk.Checkbutton(row, text="Backup Cifrato",
                        variable=self.var_backup_encrypted,
                        command=self._toggle_encryption).pack(side="left")
        
        self.encryption_frame = ttk.Frame(lf_opts)
        self.encryption_frame.pack(fill="x", pady=2)
        ttk.Label(self.encryption_frame, text="Password:", width=15).pack(side="left")
        self.entry_backup_pwd = ttk.Entry(self.encryption_frame,
                                          textvariable=self.var_backup_password,
                                          show="*", width=30, state="disabled")
        self.entry_backup_pwd.pack(side="left", padx=5)
        
        # Bottoni
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=10)
        
        self.btn_start_backup = ttk.Button(
            btn_frame, text="▶️ Avvia Backup",
            command=self.cmd_start_backup, style="Accent.TButton"
        )
        self.btn_start_backup.pack(side="left", padx=5)
        
        # Progress
        self.backup_progress = ttk.Progressbar(frame, mode="indeterminate")
        self.backup_progress.pack(fill="x", pady=5)
        
        # Output
        self.backup_output = scrolledtext.ScrolledText(
            frame, height=15,
            font=("Consolas", 9),
            bg="#1a1a2e", fg="#eaeaea",
            wrap="word"
        )
        self.backup_output.pack(fill="both", expand=True, pady=5)
    
    def _build_tab_screenshot(self):
        """Tab screenshot e screen recording."""
        frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(frame, text=" 📸 Screenshot ")
        
        # Screenshot singolo
        lf_ss = ttk.LabelFrame(frame, text=" Screenshot Singolo ", padding=10)
        lf_ss.pack(fill="x", pady=(0, 10))
        
        ttk.Button(lf_ss, text="📸 Cattura Screenshot",
                   command=self.cmd_take_screenshot, style="Accent.TButton").pack(pady=5)
        
        # Screen Recording
        lf_rec = ttk.LabelFrame(frame, text=" Screen Recording (Screenshot Sequenziali) ", padding=10)
        lf_rec.pack(fill="x", pady=(0, 10))
        
        row = ttk.Frame(lf_rec)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Intervallo (sec):", width=18).pack(side="left")
        ttk.Spinbox(row, from_=0.3, to=5.0, increment=0.1,
                    textvariable=self.var_record_interval, width=10).pack(side="left", padx=5)
        
        row = ttk.Frame(lf_rec)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="FPS Video Output:", width=18).pack(side="left")
        ttk.Spinbox(row, from_=1, to=10, increment=1,
                    textvariable=self.var_record_fps, width=10).pack(side="left", padx=5)
        
        btn_frame = ttk.Frame(lf_rec)
        btn_frame.pack(fill="x", pady=5)
        
        self.btn_start_rec = ttk.Button(
            btn_frame, text="⏺️ Avvia Registrazione",
            command=self.cmd_start_recording, style="Accent.TButton"
        )
        self.btn_start_rec.pack(side="left", padx=5)
        
        self.btn_stop_rec = ttk.Button(
            btn_frame, text="⏹️ Ferma Registrazione",
            command=self.cmd_stop_recording, state="disabled", style="Danger.TButton"
        )
        self.btn_stop_rec.pack(side="left", padx=5)
        
        self.btn_make_video = ttk.Button(
            btn_frame, text="🎬 Crea Video (ffmpeg)",
            command=self.cmd_create_video, state="disabled"
        )
        self.btn_make_video.pack(side="left", padx=5)
        
        # Status
        self.rec_status = tk.StringVar(value="Registrazione non attiva")
        ttk.Label(lf_rec, textvariable=self.rec_status, style="Status.TLabel").pack(pady=5)
    
    def _build_tab_syslog(self):
        """Tab system log e crash reports."""
        frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(frame, text=" 📋 SysLog/Crash ")
        
        # Syslog
        lf_sys = ttk.LabelFrame(frame, text=" Cattura System Log ", padding=10)
        lf_sys.pack(fill="x", pady=(0, 10))
        
        row = ttk.Frame(lf_sys)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Durata (secondi):", width=18).pack(side="left")
        ttk.Spinbox(row, from_=5, to=600, increment=5,
                    textvariable=self.var_syslog_duration, width=10).pack(side="left", padx=5)
        
        row = ttk.Frame(lf_sys)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Filtro processo:", width=18).pack(side="left")
        ttk.Entry(row, textvariable=self.var_syslog_filter, width=30).pack(side="left", padx=5)
        ttk.Label(row, text="(opzionale)", style="Status.TLabel").pack(side="left")
        
        ttk.Button(lf_sys, text="📋 Cattura SysLog",
                   command=self.cmd_capture_syslog, style="Accent.TButton").pack(pady=5)
        
        # Crash Reports
        lf_crash = ttk.LabelFrame(frame, text=" Crash Reports ", padding=10)
        lf_crash.pack(fill="x", pady=(0, 10))
        
        ttk.Button(lf_crash, text="💥 Estrai Crash Reports",
                   command=self.cmd_extract_crash_reports, style="Accent.TButton").pack(pady=5)
        
        # Diagnostics
        lf_diag = ttk.LabelFrame(frame, text=" Diagnostica Dispositivo ", padding=10)
        lf_diag.pack(fill="x")
        
        ttk.Button(lf_diag, text="🔧 Acquisisci Diagnostica",
                   command=self.cmd_get_diagnostics, style="Accent.TButton").pack(pady=5)
    
    def _build_tab_apps(self):
        """Tab lista applicazioni."""
        frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(frame, text=" 📦 App Installate ")
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Button(btn_frame, text="👤 App Utente",
                   command=lambda: self.cmd_list_apps("user")).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="⚙️ App Sistema",
                   command=lambda: self.cmd_list_apps("system")).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="📦 Tutte le App",
                   command=lambda: self.cmd_list_apps("all")).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="💾 Salva Lista",
                   command=self.cmd_save_app_list).pack(side="right", padx=5)
        
        self.apps_text = scrolledtext.ScrolledText(
            frame, height=25,
            font=("Consolas", 10),
            wrap="word"
        )
        self.apps_text.pack(fill="both", expand=True)
    
    def _build_tab_files(self):
        """Tab File & Media - accesso AFC e analisi backup."""
        frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(frame, text=" 📂 File & Media ")
        
        # ── AFC Mount ──
        lf_afc = ttk.LabelFrame(frame, text=" Apple File Conduit (AFC) - Accesso File ", padding=10)
        lf_afc.pack(fill="x", pady=(0, 10))
        
        info_afc = ttk.Label(
            lf_afc,
            text="AFC permette l'accesso ai file condivisi dalle app e alla cartella Media.\n"
                 "Richiede 'ifuse' installato (apt install ifuse / brew install ifuse).",
            style="Status.TLabel"
        )
        info_afc.pack(anchor="w", pady=(0, 5))
        
        btn_afc_frame = ttk.Frame(lf_afc)
        btn_afc_frame.pack(fill="x", pady=5)
        
        self.btn_afc_mount = ttk.Button(
            btn_afc_frame, text="📁 Monta AFC (Media)",
            command=self.cmd_mount_afc, style="Accent.TButton"
        )
        self.btn_afc_mount.pack(side="left", padx=5)
        
        self.btn_afc_scan = ttk.Button(
            btn_afc_frame, text="🔍 Scansiona File",
            command=self.cmd_scan_afc, state="disabled"
        )
        self.btn_afc_scan.pack(side="left", padx=5)
        
        self.btn_afc_copy = ttk.Button(
            btn_afc_frame, text="📋 Copia Media",
            command=self.cmd_copy_afc_media, state="disabled"
        )
        self.btn_afc_copy.pack(side="left", padx=5)
        
        self.btn_afc_unmount = ttk.Button(
            btn_afc_frame, text="⏏️ Smonta AFC",
            command=self.cmd_unmount_afc, state="disabled"
        )
        self.btn_afc_unmount.pack(side="left", padx=5)
        
        self.afc_mounted = False
        self.afc_mount_point = None
        self.afc_status_var = tk.StringVar(value="AFC non montato")
        ttk.Label(lf_afc, textvariable=self.afc_status_var, style="Status.TLabel").pack(anchor="w")
        
        # ── Analisi Backup ──
        lf_backup_analysis = ttk.LabelFrame(frame, text=" Analisi Backup Acquisito ", padding=10)
        lf_backup_analysis.pack(fill="x", pady=(0, 10))
        
        btn_ba_frame = ttk.Frame(lf_backup_analysis)
        btn_ba_frame.pack(fill="x", pady=5)
        
        ttk.Button(btn_ba_frame, text="📊 Analizza Backup",
                   command=self.cmd_analyze_backup).pack(side="left", padx=5)
        ttk.Button(btn_ba_frame, text="🖼️ Estrai Media dal Backup",
                   command=self.cmd_extract_media_backup).pack(side="left", padx=5)
        
        # ── Provisioning Profiles ──
        lf_prov = ttk.LabelFrame(frame, text=" Provisioning Profiles & Attivazione ", padding=10)
        lf_prov.pack(fill="x", pady=(0, 10))
        
        btn_prov_frame = ttk.Frame(lf_prov)
        btn_prov_frame.pack(fill="x", pady=5)
        
        ttk.Button(btn_prov_frame, text="📜 Estrai Provisioning Profiles",
                   command=self.cmd_extract_provisioning).pack(side="left", padx=5)
        ttk.Button(btn_prov_frame, text="🔑 Info Attivazione",
                   command=self.cmd_get_activation).pack(side="left", padx=5)
        
        # ── Output area ──
        self.files_text = scrolledtext.ScrolledText(
            frame, height=12,
            font=("Consolas", 9),
            wrap="word"
        )
        self.files_text.pack(fill="both", expand=True, pady=(5, 0))
    
    def _build_tab_integrity(self):
        """Tab verifica integrità hash."""
        frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(frame, text=" 🔒 Integrità ")
        
        info_lbl = ttk.Label(
            frame,
            text="Verifica l'integrità dei dati acquisiti tramite hash crittografici.\n"
                 "Crea manifest di hash e verifica che i file non siano stati alterati.",
            style="Subtitle.TLabel"
        )
        info_lbl.pack(pady=(0, 10))
        
        # ── Creazione Manifest ──
        lf_create = ttk.LabelFrame(frame, text=" Crea Hash Manifest ", padding=10)
        lf_create.pack(fill="x", pady=(0, 10))
        
        row = ttk.Frame(lf_create)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Algoritmi:", width=15).pack(side="left")
        self.var_hash_md5 = tk.BooleanVar(value=True)
        self.var_hash_sha1 = tk.BooleanVar(value=True)
        self.var_hash_sha256 = tk.BooleanVar(value=True)
        ttk.Checkbutton(row, text="MD5", variable=self.var_hash_md5).pack(side="left", padx=5)
        ttk.Checkbutton(row, text="SHA-1", variable=self.var_hash_sha1).pack(side="left", padx=5)
        ttk.Checkbutton(row, text="SHA-256", variable=self.var_hash_sha256).pack(side="left", padx=5)
        
        btn_create_frame = ttk.Frame(lf_create)
        btn_create_frame.pack(fill="x", pady=5)
        
        ttk.Button(btn_create_frame, text="📝 Crea Manifest Intero Caso",
                   command=self.cmd_create_full_manifest,
                   style="Accent.TButton").pack(side="left", padx=5)
        
        # ── Verifica ──
        lf_verify = ttk.LabelFrame(frame, text=" Verifica Integrità ", padding=10)
        lf_verify.pack(fill="x", pady=(0, 10))
        
        btn_verify_frame = ttk.Frame(lf_verify)
        btn_verify_frame.pack(fill="x", pady=5)
        
        ttk.Button(btn_verify_frame, text="✅ Verifica Ultimo Manifest",
                   command=self.cmd_verify_manifest,
                   style="Accent.TButton").pack(side="left", padx=5)
        ttk.Button(btn_verify_frame, text="📂 Verifica da File...",
                   command=self.cmd_verify_manifest_file).pack(side="left", padx=5)
        
        # ── Analisi Processi da Syslog ──
        lf_proc = ttk.LabelFrame(frame, text=" Analisi Processi da SysLog ", padding=10)
        lf_proc.pack(fill="x", pady=(0, 10))
        
        ttk.Button(lf_proc, text="🔬 Analizza Processi da Syslog",
                   command=self.cmd_analyze_processes).pack(pady=5)
        
        # Output
        self.integrity_text = scrolledtext.ScrolledText(
            frame, height=12,
            font=("Consolas", 9),
            wrap="word"
        )
        self.integrity_text.pack(fill="both", expand=True, pady=(5, 0))
    
    def _build_tab_report(self):
        """Tab generazione report."""
        frame = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(frame, text=" 📄 Report ")
        
        info_lbl = ttk.Label(
            frame,
            text="Genera il report forense finale con tutti gli artefatti acquisiti,\n"
                 "i valori hash e il log completo delle operazioni.",
            style="Subtitle.TLabel"
        )
        info_lbl.pack(pady=10)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="📄 Genera Report TXT",
                   command=lambda: self.cmd_generate_report("txt"),
                   style="Accent.TButton").pack(side="left", padx=10)
        ttk.Button(btn_frame, text="🌐 Genera Report HTML",
                   command=lambda: self.cmd_generate_report("html"),
                   style="Accent.TButton").pack(side="left", padx=10)
        ttk.Button(btn_frame, text="📄+🌐 Genera Entrambi",
                   command=lambda: self.cmd_generate_report("both"),
                   style="Accent.TButton").pack(side="left", padx=10)
        
        # Riepilogo artefatti
        lf_artifacts = ttk.LabelFrame(frame, text=" Artefatti Acquisiti ", padding=10)
        lf_artifacts.pack(fill="both", expand=True, pady=10)
        
        self.artifacts_text = scrolledtext.ScrolledText(
            lf_artifacts, height=15,
            font=("Consolas", 9),
            wrap="word"
        )
        self.artifacts_text.pack(fill="both", expand=True)
    
    # ── Helper Methods ──
    
    def _browse_output_dir(self):
        d = filedialog.askdirectory(title="Seleziona directory output")
        if d:
            self.var_output_dir.set(d)
            self.output_base_dir = d
    
    def _toggle_encryption(self):
        if self.var_backup_encrypted.get():
            self.entry_backup_pwd.config(state="normal")
        else:
            self.entry_backup_pwd.config(state="disabled")
            self.var_backup_password.set("")
    
    def log_message(self, msg):
        """Aggiunge messaggio al log."""
        timestamp = get_timestamp_full()
        full_msg = f"[{timestamp}] {msg}"
        self.acquisition_log.append(full_msg)
        
        if self.log_text is not None:
            try:
                self.log_text.insert("end", full_msg + "\n")
                self.log_text.see("end")
            except:
                pass
    
    def _update_artifacts_display(self):
        """Aggiorna display artefatti nel tab Report."""
        self.artifacts_text.delete("1.0", "end")
        
        if not self._artifacts_list:
            self.artifacts_text.insert("end", "Nessun artefatto acquisito.\n")
            return
        
        for i, art in enumerate(self._artifacts_list, 1):
            self.artifacts_text.insert("end", f"[{i}] {art['name']}\n")
            self.artifacts_text.insert("end", f"    Percorso: {art['path']}\n")
            for algo, h in art.get('hashes', {}).items():
                self.artifacts_text.insert("end", f"    {algo.upper()}: {h}\n")
            self.artifacts_text.insert("end", "\n")
    
    def _register_artifact(self, name, path, description=""):
        """Registra un artefatto acquisito."""
        hashes = calculate_hash(path) if os.path.isfile(path) else {"note": "directory"}
        
        self._artifacts_list.append({
            "name": name,
            "path": path,
            "hashes": hashes,
            "description": description,
            "timestamp": get_timestamp_full(),
        })
        
        self._update_artifacts_display()
        
        if os.path.isfile(path):
            self.log_message(f"[HASH] {name}:")
            for algo, h in hashes.items():
                self.log_message(f"       {algo.upper()}: {h}")
    
    def _ensure_case_dir(self):
        """Verifica che la directory del caso sia stata inizializzata."""
        if not self.current_case_dir:
            messagebox.showwarning("Attenzione",
                                   "Inizializza prima il caso nel tab 'Caso'!")
            self.notebook.select(0)
            return False
        return True
    
    def _check_dependencies(self):
        """Verifica dipendenze all'avvio."""
        missing = []
        for name, binary in IDEVICE_TOOLS.items():
            if not check_tool_available(binary):
                missing.append(binary)
        
        if missing:
            self.log_message(f"[WARNING] Tool mancanti: {', '.join(missing)}")
            self.log_message("[INFO] Installa libimobiledevice per funzionalità complete")
            self.log_message("[INFO]   Tsurugi: sudo apt install libimobiledevice-utils ideviceinstaller")
            self.log_message("[INFO]   macOS:   brew install libimobiledevice ideviceinstaller")
        
        if check_tool_available("ffmpeg"):
            self.log_message("[INFO] ffmpeg disponibile - screen recording video abilitato")
        else:
            self.log_message("[WARNING] ffmpeg non trovato - creazione video non disponibile")
        
        if check_tool_available("ifuse"):
            self.log_message("[INFO] ifuse disponibile - accesso file AFC abilitato")
        else:
            self.log_message("[WARNING] ifuse non trovato - accesso file AFC non disponibile")
            if self.platform_info["is_linux"]:
                self.log_message("[INFO]   Installa con: sudo apt install ifuse")
            elif self.platform_info["is_mac"]:
                self.log_message("[INFO]   Installa con: brew install ifuse")
    
    def _run_in_thread(self, target, *args, **kwargs):
        """Esegue una funzione in un thread separato."""
        thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
        thread.start()
        return thread
    
    # ── Commands ──
    
    def cmd_detect_device(self):
        """Rileva dispositivo iOS."""
        self.log_message("[ACTION] Rilevamento dispositivo iOS...")
        self.var_device_status.set("🔍 Ricerca in corso...")
        
        def _detect():
            success, result = self.device.detect_device()
            if success:
                self.var_device_status.set(f"✅ Connesso - UDID: {result}")
                self.status_label.config(fg=COLORS["success"])
                # Prova a ottenere il nome
                name = self.device.get_device_name()
                self.log_message(f"[OK] Dispositivo: {name} (UDID: {result})")
                # Auto-fetch info
                self.cmd_get_device_info()
            else:
                self.var_device_status.set(f"❌ {result}")
                self.status_label.config(fg=COLORS["error"])
        
        self._run_in_thread(_detect)
    
    def cmd_pair_device(self):
        """Pairing con dispositivo."""
        if not self.device.udid:
            messagebox.showinfo("Info", "Prima rileva il dispositivo.")
            return
        
        self.log_message("[ACTION] Tentativo pairing...")
        
        def _pair():
            # Valida prima
            valid, msg = self.device.validate_pair()
            if valid:
                self.log_message("[OK] Pairing già valido")
                messagebox.showinfo("Pairing", "Il pairing è già valido!")
                return
            
            success, msg = self.device.pair_device()
            if success:
                self.log_message(f"[OK] Pairing: {msg}")
                messagebox.showinfo("Pairing",
                                    "Pairing completato!\n\n"
                                    "Se richiesto, sblocca il dispositivo\n"
                                    "e tocca 'Autorizza' / 'Trust'.")
            else:
                self.log_message(f"[ERROR] Pairing: {msg}")
                messagebox.showerror("Errore Pairing",
                                     f"{msg}\n\nAssicurati che il dispositivo sia "
                                     "sbloccato e tocca 'Autorizza'.")
        
        self._run_in_thread(_pair)
    
    def cmd_init_case(self):
        """Inizializza struttura directory del caso."""
        case_num = self.var_case_number.get().strip()
        if not case_num:
            messagebox.showwarning("Attenzione", "Inserisci un numero caso!")
            return
        
        base = self.var_output_dir.get()
        ts = get_timestamp()
        case_dirname = f"Case_{case_num}_{ts}"
        self.current_case_dir = os.path.join(base, case_dirname)
        
        # Crea struttura directory
        subdirs = [
            "backup",
            "backup_media",
            "device_info",
            "screenshots",
            "screen_recording",
            "screen_recording/frames",
            "syslog",
            "crash_reports",
            "app_list",
            "diagnostics",
            "provisioning_profiles",
            "afc_media",
            "reports",
            "hashes",
        ]
        
        for d in subdirs:
            os.makedirs(os.path.join(self.current_case_dir, d), exist_ok=True)
        
        self.log_message(f"[CASE] Caso inizializzato: {self.current_case_dir}")
        self.log_message(f"[CASE] Numero: {case_num}")
        self.log_message(f"[CASE] Esaminatore: {self.var_examiner_name.get()}")
        
        messagebox.showinfo("Caso Inizializzato",
                           f"Directory caso creata:\n{self.current_case_dir}")
    
    def cmd_get_device_info(self):
        """Recupera e mostra info dispositivo."""
        if not self.device.udid:
            self.device_info_text.delete("1.0", "end")
            self.device_info_text.insert("end", "Nessun dispositivo connesso.\n"
                                                "Usa 'Rileva Dispositivo' prima.")
            return
        
        self.log_message("[ACTION] Lettura informazioni dispositivo...")
        
        def _get_info():
            self.device_info_text.delete("1.0", "end")
            
            # Info generali
            success, info = self.device.get_device_info()
            if not success:
                self.device_info_text.insert("end", f"Errore: {info}\n")
                return
            
            header = "═" * 55 + "\n"
            header += "  INFORMAZIONI DISPOSITIVO iOS\n"
            header += "═" * 55 + "\n\n"
            self.device_info_text.insert("end", header)
            
            # Campi principali
            important_keys = [
                "DeviceName", "DeviceClass", "ProductType", "ModelNumber",
                "HardwareModel", "ProductVersion", "BuildVersion",
                "SerialNumber", "UniqueDeviceID", "WiFiAddress",
                "BluetoothAddress", "PhoneNumber", "CPUArchitecture",
                "DeviceColor", "ActivationState", "BasebandVersion",
                "FirmwareVersion", "RegionInfo", "TimeZone",
                "PasswordProtected", "ProductionSOC",
            ]
            
            self.device_info_text.insert("end", "── Informazioni Principali ──\n\n")
            for key in important_keys:
                if key in info:
                    self.device_info_text.insert("end", f"  {key}: {info[key]}\n")
            
            # Data dispositivo
            dev_date = self.device.get_device_date()
            if dev_date:
                self.device_info_text.insert("end", f"  DeviceDate: {dev_date}\n")
            
            # Tutte le altre info
            self.device_info_text.insert("end", "\n── Tutte le Informazioni ──\n\n")
            for key, value in sorted(info.items()):
                self.device_info_text.insert("end", f"  {key}: {value}\n")
            
            # Domini specifici
            domains = [
                ("com.apple.disk_usage", "Uso Disco"),
                ("com.apple.battery", "Batteria"),
                ("com.apple.international", "Internazionale"),
            ]
            
            for domain, label in domains:
                ok, domain_info = self.device.get_device_info(domain=domain)
                if ok and domain_info:
                    self.device_info_text.insert("end", f"\n── {label} ({domain}) ──\n\n")
                    for k, v in domain_info.items():
                        self.device_info_text.insert("end", f"  {k}: {v}\n")
            
            self.log_message(f"[OK] Info dispositivo lette ({len(info)} campi)")
        
        self._run_in_thread(_get_info)
    
    def cmd_save_device_info(self):
        """Salva info dispositivo su file."""
        if not self._ensure_case_dir():
            return
        
        content = self.device_info_text.get("1.0", "end").strip()
        if not content or "Nessun dispositivo" in content:
            messagebox.showwarning("Attenzione", "Nessuna info dispositivo da salvare.")
            return
        
        ts = get_timestamp()
        txt_path = os.path.join(self.current_case_dir, "device_info", f"device_info_{ts}.txt")
        
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"# Device Info - Acquisito il {get_timestamp_full()}\n")
            f.write(f"# UDID: {self.device.udid}\n\n")
            f.write(content)
        
        # Salva anche in JSON
        if self.device.device_info:
            json_path = os.path.join(self.current_case_dir, "device_info", f"device_info_{ts}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(self.device.device_info, f, indent=2, ensure_ascii=False)
            self._register_artifact("Device Info (JSON)", json_path, "Info dispositivo formato JSON")
        
        self._register_artifact("Device Info (TXT)", txt_path, "Info dispositivo formato testo")
        
        self.log_message(f"[OK] Info dispositivo salvate: {txt_path}")
        messagebox.showinfo("Salvato", f"Info dispositivo salvate in:\n{txt_path}")
    
    def cmd_start_backup(self):
        """Avvia backup iOS."""
        if not self._ensure_case_dir():
            return
        if not self.device.udid:
            messagebox.showwarning("Attenzione", "Nessun dispositivo connesso!")
            return
        
        encrypted = self.var_backup_encrypted.get()
        password = self.var_backup_password.get() if encrypted else None
        
        if encrypted and not password:
            messagebox.showwarning("Attenzione", "Inserisci la password per il backup cifrato!")
            return
        
        backup_dir = os.path.join(self.current_case_dir, "backup")
        
        self.btn_start_backup.config(state="disabled")
        self.backup_progress.start(10)
        self.backup_output.delete("1.0", "end")
        
        self.log_message(f"[ACTION] Avvio backup {'cifrato' if encrypted else 'non cifrato'}...")
        self.log_message(f"[INFO] Directory: {backup_dir}")
        
        def _progress(line):
            self.backup_output.insert("end", line + "\n")
            self.backup_output.see("end")
        
        def _do_backup():
            success, result = self.device.start_backup(
                backup_dir,
                encrypted=encrypted,
                password=password,
                full=self.var_backup_full.get(),
                progress_callback=_progress,
            )
            
            self.backup_progress.stop()
            self.btn_start_backup.config(state="normal")
            
            if success:
                self.log_message("[OK] Backup completato!")
                
                # Calcola hash della directory di backup
                self.log_message("[HASH] Calcolo hash file backup...")
                hash_results = calculate_dir_hashes(backup_dir)
                
                hash_file = os.path.join(self.current_case_dir, "hashes", f"backup_hashes_{get_timestamp()}.txt")
                with open(hash_file, "w") as f:
                    for entry in hash_results:
                        for algo, h in entry["hashes"].items():
                            f.write(f"{h}  {entry['file']}\n")
                
                self._register_artifact("iOS Backup", backup_dir,
                                        f"Backup {'cifrato' if encrypted else 'standard'} - "
                                        f"{len(hash_results)} file")
                self._register_artifact("Hash Backup", hash_file, "Hash SHA-256 file backup")
                
                total_size = sum(e["size"] for e in hash_results)
                self.backup_output.insert("end", f"\n{'='*50}\n")
                self.backup_output.insert("end", f"Backup completato!\n")
                self.backup_output.insert("end", f"File: {len(hash_results)}\n")
                self.backup_output.insert("end", f"Dimensione totale: {total_size / (1024*1024):.1f} MB\n")
                self.backup_output.insert("end", f"Hash salvati in: {hash_file}\n")
                
                messagebox.showinfo("Backup Completato",
                                    f"Backup acquisito con successo!\n\n"
                                    f"File: {len(hash_results)}\n"
                                    f"Dimensione: {total_size / (1024*1024):.1f} MB")
            else:
                self.log_message(f"[ERROR] Backup fallito: {result}")
                self.backup_output.insert("end", f"\nERRORE: {result}\n")
                messagebox.showerror("Errore", f"Backup fallito:\n{result}")
        
        self._run_in_thread(_do_backup)
    
    def cmd_take_screenshot(self):
        """Cattura singolo screenshot."""
        if not self._ensure_case_dir():
            return
        if not self.device.udid:
            messagebox.showwarning("Attenzione", "Nessun dispositivo connesso!")
            return
        
        ts = get_timestamp()
        ss_path = os.path.join(self.current_case_dir, "screenshots", f"screenshot_{ts}.png")
        
        self.log_message("[ACTION] Cattura screenshot...")
        
        def _capture():
            success, result = self.device.take_screenshot(ss_path)
            if success:
                self._register_artifact(f"Screenshot {ts}", ss_path, "Screenshot singolo")
                self.log_message(f"[OK] Screenshot salvato: {result}")
                messagebox.showinfo("Screenshot", f"Screenshot salvato:\n{result}")
            else:
                self.log_message(f"[ERROR] Screenshot: {result}")
                messagebox.showerror("Errore", f"Screenshot fallito:\n{result}")
        
        self._run_in_thread(_capture)
    
    def cmd_start_recording(self):
        """Avvia screen recording."""
        if not self._ensure_case_dir():
            return
        if not self.device.udid:
            messagebox.showwarning("Attenzione", "Nessun dispositivo connesso!")
            return
        
        frames_dir = os.path.join(self.current_case_dir, "screen_recording", "frames")
        
        self.screen_recorder = ScreenRecorder(
            self.device,
            frames_dir,
            interval=self.var_record_interval.get(),
            logger=self.log_message
        )
        
        self.screen_recorder.start()
        self.is_recording = True
        
        self.btn_start_rec.config(state="disabled")
        self.btn_stop_rec.config(state="normal")
        self.rec_status.set("⏺️ REGISTRAZIONE IN CORSO...")
        
        self.log_message("[ACTION] Screen recording avviato")
    
    def cmd_stop_recording(self):
        """Ferma screen recording."""
        if not self.screen_recorder:
            return
        
        frame_count = self.screen_recorder.stop()
        self.is_recording = False
        
        self.btn_start_rec.config(state="normal")
        self.btn_stop_rec.config(state="disabled")
        self.btn_make_video.config(state="normal")
        self.rec_status.set(f"⏹️ Registrazione fermata - {frame_count} frame catturati")
        
        if frame_count > 0:
            frames_dir = self.screen_recorder.output_dir
            self._register_artifact(
                f"Screen Recording Frames ({frame_count})",
                frames_dir,
                f"{frame_count} frame catturati ad intervallo {self.var_record_interval.get()}s"
            )
        
        self.log_message(f"[OK] Screen recording: {frame_count} frame catturati")
    
    def cmd_create_video(self):
        """Crea video da frame catturati."""
        if not self.screen_recorder:
            return
        
        video_path = os.path.join(self.current_case_dir, "screen_recording",
                                  f"recording_{get_timestamp()}.mp4")
        
        self.log_message("[ACTION] Creazione video...")
        self.rec_status.set("🎬 Creazione video in corso...")
        
        def _create():
            success, result = self.screen_recorder.create_video(
                video_path,
                fps=self.var_record_fps.get()
            )
            
            if success:
                self._register_artifact("Screen Recording Video", result, "Video screen recording")
                self.rec_status.set(f"✅ Video creato: {os.path.basename(result)}")
                messagebox.showinfo("Video", f"Video creato:\n{result}")
            else:
                self.rec_status.set(f"❌ Errore: {result}")
                messagebox.showerror("Errore", f"Creazione video fallita:\n{result}")
        
        self._run_in_thread(_create)
    
    def cmd_capture_syslog(self):
        """Cattura system log."""
        if not self._ensure_case_dir():
            return
        if not self.device.udid:
            messagebox.showwarning("Attenzione", "Nessun dispositivo connesso!")
            return
        
        duration = self.var_syslog_duration.get()
        process_filter = self.var_syslog_filter.get().strip() or None
        
        ts = get_timestamp()
        log_path = os.path.join(self.current_case_dir, "syslog", f"syslog_{ts}.txt")
        
        self.log_message(f"[ACTION] Cattura syslog ({duration}s)...")
        
        if process_filter:
            self.log_message(f"[INFO] Filtro processo: {process_filter}")
        
        messagebox.showinfo("SysLog",
                           f"La cattura del log di sistema durerà {duration} secondi.\n"
                           "Interagisci con il dispositivo durante la cattura\n"
                           "per registrare attività rilevanti.")
        
        def _capture():
            success, result = self.device.capture_syslog(
                log_path,
                duration=duration,
                process_filter=process_filter
            )
            
            if success:
                self._register_artifact(f"System Log ({duration}s)", result,
                                        f"Cattura {duration}s" +
                                        (f" filtro: {process_filter}" if process_filter else ""))
                self.log_message(f"[OK] Syslog salvato: {result}")
                messagebox.showinfo("SysLog", f"Log di sistema salvato:\n{result}")
            else:
                self.log_message(f"[ERROR] Syslog: {result}")
                messagebox.showerror("Errore", f"Cattura syslog fallita:\n{result}")
        
        self._run_in_thread(_capture)
    
    def cmd_extract_crash_reports(self):
        """Estrae crash reports."""
        if not self._ensure_case_dir():
            return
        if not self.device.udid:
            messagebox.showwarning("Attenzione", "Nessun dispositivo connesso!")
            return
        
        crash_dir = os.path.join(self.current_case_dir, "crash_reports")
        
        self.log_message("[ACTION] Estrazione crash reports...")
        
        def _extract():
            success, result = self.device.extract_crash_reports(crash_dir)
            if success:
                self._register_artifact("Crash Reports", crash_dir, result)
                self.log_message(f"[OK] {result}")
                messagebox.showinfo("Crash Reports", f"Crash reports estratti:\n{result}")
            else:
                self.log_message(f"[ERROR] Crash reports: {result}")
                messagebox.showerror("Errore", f"Estrazione fallita:\n{result}")
        
        self._run_in_thread(_extract)
    
    def cmd_get_diagnostics(self):
        """Acquisisce info diagnostiche."""
        if not self._ensure_case_dir():
            return
        if not self.device.udid:
            messagebox.showwarning("Attenzione", "Nessun dispositivo connesso!")
            return
        
        ts = get_timestamp()
        diag_path = os.path.join(self.current_case_dir, "diagnostics", f"diagnostics_{ts}.txt")
        
        self.log_message("[ACTION] Acquisizione diagnostica...")
        
        def _diag():
            success, result = self.device.get_diagnostics()
            if success:
                with open(diag_path, "w", encoding="utf-8") as f:
                    f.write(f"# Diagnostica iOS - {get_timestamp_full()}\n")
                    f.write(f"# UDID: {self.device.udid}\n\n")
                    f.write(result)
                
                self._register_artifact("Diagnostica", diag_path, "Info diagnostiche dispositivo")
                self.log_message(f"[OK] Diagnostica salvata: {diag_path}")
                messagebox.showinfo("Diagnostica", f"Diagnostica salvata:\n{diag_path}")
            else:
                self.log_message(f"[ERROR] Diagnostica: {result}")
                messagebox.showerror("Errore", f"Diagnostica fallita:\n{result}")
        
        self._run_in_thread(_diag)
    
    def cmd_list_apps(self, app_type="user"):
        """Lista applicazioni installate."""
        if not self.device.udid:
            self.apps_text.delete("1.0", "end")
            self.apps_text.insert("end", "Nessun dispositivo connesso.\n")
            return
        
        self.log_message(f"[ACTION] Lettura app ({app_type})...")
        self.apps_text.delete("1.0", "end")
        self.apps_text.insert("end", "Caricamento...\n")
        
        def _list():
            success, result = self.device.get_installed_apps(app_type)
            self.apps_text.delete("1.0", "end")
            
            if success:
                label = {"user": "Utente", "system": "Sistema", "all": "Tutte"}.get(app_type, app_type)
                header = f"{'═'*55}\n  Applicazioni {label}\n{'═'*55}\n\n"
                self.apps_text.insert("end", header)
                
                for i, app in enumerate(result, 1):
                    self.apps_text.insert("end",
                        f"  [{i:3d}] {app['bundle_id']}\n"
                        f"        {app['name_version']}\n\n")
                
                self.apps_text.insert("end", f"\nTotale: {len(result)} applicazioni\n")
                self.log_message(f"[OK] App {app_type}: {len(result)} trovate")
            else:
                self.apps_text.insert("end", f"Errore: {result}\n")
                self.log_message(f"[ERROR] App list: {result}")
        
        self._run_in_thread(_list)
    
    def cmd_save_app_list(self):
        """Salva lista app su file."""
        if not self._ensure_case_dir():
            return
        
        content = self.apps_text.get("1.0", "end").strip()
        if not content or "Nessun dispositivo" in content or "Caricamento" in content:
            messagebox.showwarning("Attenzione", "Nessuna lista app da salvare.")
            return
        
        ts = get_timestamp()
        app_path = os.path.join(self.current_case_dir, "app_list", f"app_list_{ts}.txt")
        
        with open(app_path, "w", encoding="utf-8") as f:
            f.write(f"# Lista App iOS - {get_timestamp_full()}\n")
            f.write(f"# UDID: {self.device.udid}\n\n")
            f.write(content)
        
        self._register_artifact("Lista Applicazioni", app_path, "App installate sul dispositivo")
        self.log_message(f"[OK] Lista app salvata: {app_path}")
        messagebox.showinfo("Salvato", f"Lista app salvata:\n{app_path}")
    
    # ── Commands: File & Media Tab ──
    
    def cmd_mount_afc(self):
        """Monta filesystem AFC."""
        if not self._ensure_case_dir():
            return
        if not self.device.udid:
            messagebox.showwarning("Attenzione", "Nessun dispositivo connesso!")
            return
        
        self.afc_mount_point = os.path.join(self.current_case_dir, ".afc_mount")
        
        self.log_message("[ACTION] Mount AFC...")
        self.files_text.delete("1.0", "end")
        self.files_text.insert("end", "Montaggio AFC in corso...\n")
        
        def _mount():
            success, result = self.device.mount_afc(self.afc_mount_point)
            if success:
                self.afc_mounted = True
                self.afc_status_var.set(f"✅ AFC montato: {self.afc_mount_point}")
                self.btn_afc_scan.config(state="normal")
                self.btn_afc_copy.config(state="normal")
                self.btn_afc_unmount.config(state="normal")
                self.btn_afc_mount.config(state="disabled")
                
                self.files_text.delete("1.0", "end")
                self.files_text.insert("end", f"AFC montato in: {self.afc_mount_point}\n\n")
                self.files_text.insert("end", "Usa 'Scansiona File' per esplorare il contenuto.\n")
                self.log_message(f"[OK] AFC montato: {self.afc_mount_point}")
            else:
                self.afc_status_var.set(f"❌ Errore: {result}")
                self.files_text.delete("1.0", "end")
                self.files_text.insert("end", f"Errore mount AFC:\n{result}\n\n")
                self.files_text.insert("end", "Suggerimenti:\n")
                self.files_text.insert("end", "  - Installa ifuse: apt install ifuse (Linux) / brew install ifuse (macOS)\n")
                self.files_text.insert("end", "  - Verifica che il dispositivo sia sbloccato e autorizzato\n")
                self.files_text.insert("end", "  - Su macOS potrebbe servire: brew install --cask macfuse\n")
                self.log_message(f"[ERROR] AFC mount: {result}")
        
        self._run_in_thread(_mount)
    
    def cmd_scan_afc(self):
        """Scansiona file nel mount AFC."""
        if not self.afc_mounted or not self.afc_mount_point:
            return
        
        self.log_message("[ACTION] Scansione file AFC...")
        self.files_text.delete("1.0", "end")
        self.files_text.insert("end", "Scansione in corso...\n")
        
        def _scan():
            files = self.device.list_afc_files(self.afc_mount_point, max_depth=4)
            
            self.files_text.delete("1.0", "end")
            header = f"{'═'*60}\n  FILE AFC - {len(files)} file trovati\n{'═'*60}\n\n"
            self.files_text.insert("end", header)
            
            # Raggruppa per tipo
            by_type = {}
            for f in files:
                t = f["type"]
                if t not in by_type:
                    by_type[t] = []
                by_type[t].append(f)
            
            for ftype, flist in sorted(by_type.items()):
                total_size = sum(f["size"] for f in flist)
                self.files_text.insert("end",
                    f"── {ftype.upper()} ({len(flist)} file, {total_size/(1024*1024):.1f} MB) ──\n")
                for f in flist[:50]:  # Limita a 50 per tipo
                    size_str = f"{f['size']/1024:.1f}K" if f['size'] < 1024*1024 else f"{f['size']/(1024*1024):.1f}M"
                    self.files_text.insert("end", f"  {size_str:>8}  {f['path']}\n")
                if len(flist) > 50:
                    self.files_text.insert("end", f"  ... e altri {len(flist)-50} file\n")
                self.files_text.insert("end", "\n")
            
            self.log_message(f"[OK] Scansione AFC: {len(files)} file trovati")
        
        self._run_in_thread(_scan)
    
    def cmd_copy_afc_media(self):
        """Copia file media dal mount AFC."""
        if not self._ensure_case_dir():
            return
        if not self.afc_mounted:
            messagebox.showwarning("Attenzione", "AFC non montato!")
            return
        
        media_dir = os.path.join(self.current_case_dir, "afc_media")
        
        self.log_message("[ACTION] Copia media da AFC...")
        self.files_text.insert("end", "\nCopia file media in corso...\n")
        
        def _copy():
            copied, errors = self.device.copy_afc_files(
                self.afc_mount_point, media_dir,
                file_types=["images", "videos", "audio", "documents"]
            )
            
            self.files_text.insert("end", f"\nCopia completata: {copied} file copiati, {errors} errori\n")
            self.files_text.insert("end", f"Directory: {media_dir}\n")
            
            if copied > 0:
                self._register_artifact("Media AFC", media_dir,
                                        f"{copied} file media estratti via AFC")
            
            self.log_message(f"[OK] AFC media: {copied} copiati, {errors} errori")
            messagebox.showinfo("Copia Media",
                               f"File copiati: {copied}\nErrori: {errors}\n\nDestinazione: {media_dir}")
        
        self._run_in_thread(_copy)
    
    def cmd_unmount_afc(self):
        """Smonta AFC."""
        if not self.afc_mounted or not self.afc_mount_point:
            return
        
        success, msg = self.device.unmount_afc(self.afc_mount_point)
        
        if success:
            self.afc_mounted = False
            self.afc_status_var.set("AFC smontato")
            self.btn_afc_mount.config(state="normal")
            self.btn_afc_scan.config(state="disabled")
            self.btn_afc_copy.config(state="disabled")
            self.btn_afc_unmount.config(state="disabled")
            self.log_message("[OK] AFC smontato")
        else:
            self.log_message(f"[ERROR] Unmount AFC: {msg}")
            messagebox.showerror("Errore", f"Errore unmount:\n{msg}")
    
    def cmd_analyze_backup(self):
        """Analizza il backup acquisito."""
        if not self._ensure_case_dir():
            return
        
        backup_dir = os.path.join(self.current_case_dir, "backup")
        if not os.path.exists(backup_dir) or not os.listdir(backup_dir):
            messagebox.showwarning("Attenzione",
                                   "Nessun backup trovato nella directory del caso.\n"
                                   "Acquisisci prima un backup dal tab 'Backup'.")
            return
        
        self.log_message("[ACTION] Analisi backup...")
        self.files_text.delete("1.0", "end")
        self.files_text.insert("end", "Analisi backup in corso...\n")
        
        def _analyze():
            stats = BackupAnalyzer.analyze_backup_dir(backup_dir)
            
            self.files_text.delete("1.0", "end")
            header = f"{'═'*60}\n  ANALISI BACKUP iOS\n{'═'*60}\n\n"
            self.files_text.insert("end", header)
            
            total_mb = stats['total_size'] / (1024*1024)
            self.files_text.insert("end", f"  File totali:        {stats['total_files']}\n")
            self.files_text.insert("end", f"  Dimensione totale:  {total_mb:.1f} MB\n")
            self.files_text.insert("end", f"  Manifest trovato:   {'✅' if stats['manifest_found'] else '❌'}\n")
            self.files_text.insert("end", f"  Info.plist:         {'✅' if stats['info_plist_found'] else '❌'}\n")
            self.files_text.insert("end", f"  Status.plist:       {'✅' if stats['status_plist_found'] else '❌'}\n")
            
            self.files_text.insert("end", "\n── Contenuto per Tipo ──\n\n")
            for cat, data in stats["by_type"].items():
                if data["count"] > 0:
                    cat_mb = data['size'] / (1024*1024)
                    self.files_text.insert("end",
                        f"  {cat:<15} {data['count']:>6} file  ({cat_mb:.1f} MB)\n")
            
            self.files_text.insert("end", "\n── Estensioni Presenti ──\n\n")
            for ext, count in sorted(stats["by_extension"].items(), key=lambda x: x[1], reverse=True)[:30]:
                self.files_text.insert("end", f"  {ext:<10} {count:>6} file\n")
            
            if stats["largest_files"]:
                self.files_text.insert("end", "\n── Top 20 File più Grandi ──\n\n")
                for fname, size in stats["largest_files"]:
                    size_mb = size / (1024*1024)
                    self.files_text.insert("end", f"  {size_mb:>8.1f} MB  {fname}\n")
            
            # Salva analisi
            analysis_path = os.path.join(self.current_case_dir, "reports",
                                          f"backup_analysis_{get_timestamp()}.json")
            # Converti per JSON (rimuovi tuple)
            stats_json = {k: v for k, v in stats.items() if k != "largest_files"}
            stats_json["largest_files"] = [{"file": f, "size": s} for f, s in stats["largest_files"]]
            with open(analysis_path, "w") as f:
                json.dump(stats_json, f, indent=2)
            
            self._register_artifact("Analisi Backup", analysis_path, 
                                    f"{stats['total_files']} file, {total_mb:.1f} MB")
            self.log_message(f"[OK] Analisi backup: {stats['total_files']} file, {total_mb:.1f} MB")
        
        self._run_in_thread(_analyze)
    
    def cmd_extract_media_backup(self):
        """Estrae file media dal backup."""
        if not self._ensure_case_dir():
            return
        
        backup_dir = os.path.join(self.current_case_dir, "backup")
        if not os.path.exists(backup_dir) or not os.listdir(backup_dir):
            messagebox.showwarning("Attenzione", "Nessun backup trovato.")
            return
        
        media_dir = os.path.join(self.current_case_dir, "backup_media")
        
        self.log_message("[ACTION] Estrazione media dal backup...")
        self.files_text.insert("end", "\nEstrazione file media dal backup...\n")
        
        def _extract():
            copied, total = BackupAnalyzer.extract_media_from_backup(
                backup_dir, media_dir,
                media_types=["images", "videos", "audio", "documents"]
            )
            
            self.files_text.insert("end", f"\nEstrazione completata: {copied}/{total} file estratti\n")
            self.files_text.insert("end", f"Directory: {media_dir}\n")
            
            if copied > 0:
                self._register_artifact("Media da Backup", media_dir,
                                        f"{copied} file media estratti dal backup")
            
            self.log_message(f"[OK] Media backup: {copied}/{total} estratti in {media_dir}")
            messagebox.showinfo("Estrazione Media",
                               f"File estratti: {copied}/{total}\n\nDestinazione: {media_dir}")
        
        self._run_in_thread(_extract)
    
    def cmd_extract_provisioning(self):
        """Estrae provisioning profiles."""
        if not self._ensure_case_dir():
            return
        if not self.device.udid:
            messagebox.showwarning("Attenzione", "Nessun dispositivo connesso!")
            return
        
        prov_dir = os.path.join(self.current_case_dir, "provisioning_profiles")
        
        self.log_message("[ACTION] Estrazione provisioning profiles...")
        
        def _extract():
            success, result = self.device.get_provisioning_profiles(prov_dir)
            
            self.files_text.delete("1.0", "end")
            
            if success:
                self.files_text.insert("end", f"Provisioning Profiles estratti: {result.get('count', 0)}\n\n")
                self.files_text.insert("end", result.get("list", ""))
                
                self._register_artifact("Provisioning Profiles", prov_dir,
                                        f"{result.get('count', 0)} profili estratti")
                self.log_message(f"[OK] Provisioning profiles: {result.get('count', 0)}")
            else:
                self.files_text.insert("end", f"Lista profili:\n{result.get('list', 'N/A')}\n\n")
                if "error" in result:
                    self.files_text.insert("end", f"Errore estrazione: {result['error']}\n")
                self.log_message(f"[WARNING] Provisioning profiles: risultato parziale")
        
        self._run_in_thread(_extract)
    
    def cmd_get_activation(self):
        """Recupera info attivazione."""
        if not self.device.udid:
            messagebox.showwarning("Attenzione", "Nessun dispositivo connesso!")
            return
        
        self.log_message("[ACTION] Lettura info attivazione...")
        
        def _get():
            success, result = self.device.get_activation_info()
            self.files_text.insert("end", f"\n── Info Attivazione ──\n{result}\n")
            if success:
                self.log_message(f"[OK] Attivazione: {result}")
            else:
                self.log_message(f"[ERROR] Attivazione: {result}")
        
        self._run_in_thread(_get)
    
    # ── Commands: Integrity Tab ──
    
    def _get_hash_algorithms(self):
        """Ritorna lista algoritmi selezionati."""
        algos = []
        if self.var_hash_md5.get():
            algos.append("md5")
        if self.var_hash_sha1.get():
            algos.append("sha1")
        if self.var_hash_sha256.get():
            algos.append("sha256")
        return algos if algos else ["sha256"]
    
    def cmd_create_full_manifest(self):
        """Crea hash manifest dell'intero caso."""
        if not self._ensure_case_dir():
            return
        
        algos = self._get_hash_algorithms()
        ts = get_timestamp()
        manifest_path = os.path.join(self.current_case_dir, "hashes",
                                      f"full_manifest_{ts}.txt")
        
        self.log_message(f"[ACTION] Creazione hash manifest ({', '.join(algos)})...")
        self.integrity_text.delete("1.0", "end")
        self.integrity_text.insert("end", "Calcolo hash in corso... (può richiedere tempo)\n")
        
        def _create():
            count, txt_path, json_path = IntegrityVerifier.create_hash_manifest(
                self.current_case_dir, manifest_path, algos
            )
            
            self.integrity_text.delete("1.0", "end")
            header = f"{'═'*60}\n  HASH MANIFEST CREATO\n{'═'*60}\n\n"
            self.integrity_text.insert("end", header)
            self.integrity_text.insert("end", f"  File analizzati:  {count}\n")
            self.integrity_text.insert("end", f"  Algoritmi:        {', '.join(algos)}\n")
            self.integrity_text.insert("end", f"  Manifest TXT:     {txt_path}\n")
            self.integrity_text.insert("end", f"  Manifest JSON:    {json_path}\n")
            
            self._register_artifact("Hash Manifest (TXT)", txt_path,
                                    f"Manifest di {count} file - {', '.join(algos)}")
            self._register_artifact("Hash Manifest (JSON)", json_path,
                                    f"Manifest JSON di {count} file")
            
            self.log_message(f"[OK] Manifest creato: {count} file hashati")
            messagebox.showinfo("Manifest Creato",
                               f"Hash manifest creato per {count} file.\n\n"
                               f"TXT: {txt_path}\nJSON: {json_path}")
        
        self._run_in_thread(_create)
    
    def cmd_verify_manifest(self):
        """Verifica ultimo manifest creato."""
        if not self._ensure_case_dir():
            return
        
        hashes_dir = os.path.join(self.current_case_dir, "hashes")
        if not os.path.exists(hashes_dir):
            messagebox.showwarning("Attenzione", "Nessun manifest trovato. Creane uno prima.")
            return
        
        # Cerca ultimo manifest JSON
        manifests = sorted([
            f for f in os.listdir(hashes_dir) if f.startswith("full_manifest_") and f.endswith(".json")
        ])
        
        if not manifests:
            messagebox.showwarning("Attenzione", "Nessun manifest JSON trovato.")
            return
        
        manifest_path = os.path.join(hashes_dir, manifests[-1])
        self._do_verify_manifest(manifest_path)
    
    def cmd_verify_manifest_file(self):
        """Verifica un manifest selezionato dall'utente."""
        fpath = filedialog.askopenfilename(
            title="Seleziona manifest JSON",
            filetypes=[("JSON", "*.json"), ("Tutti", "*.*")]
        )
        if fpath:
            self._do_verify_manifest(fpath)
    
    def _do_verify_manifest(self, manifest_path):
        """Esegue verifica di un manifest."""
        self.log_message(f"[ACTION] Verifica manifest: {manifest_path}")
        self.integrity_text.delete("1.0", "end")
        self.integrity_text.insert("end", "Verifica integrità in corso...\n")
        
        def _verify():
            ok, summary, results = IntegrityVerifier.verify_hash_manifest(manifest_path)
            
            self.integrity_text.delete("1.0", "end")
            header = f"{'═'*60}\n  VERIFICA INTEGRITÀ\n{'═'*60}\n\n"
            self.integrity_text.insert("end", header)
            
            status_icon = "✅" if ok else "❌"
            self.integrity_text.insert("end", f"  Stato: {status_icon} {summary.get('integrity', 'N/A')}\n\n")
            self.integrity_text.insert("end", f"  File verificati: {summary.get('total', 0)}\n")
            self.integrity_text.insert("end", f"  ✅ OK:           {summary.get('passed', 0)}\n")
            self.integrity_text.insert("end", f"  ❌ Alterati:     {summary.get('failed', 0)}\n")
            self.integrity_text.insert("end", f"  ⚠️  Mancanti:    {summary.get('missing', 0)}\n\n")
            
            # Mostra dettagli problemi
            problems = [r for r in results if r["status"] != "OK"]
            if problems:
                self.integrity_text.insert("end", "── Problemi Rilevati ──\n\n")
                for p in problems:
                    self.integrity_text.insert("end", f"  [{p['status']}] {p['file']}\n")
                    if p["status"] == "ALTERATO":
                        for algo in p.get("expected", {}):
                            self.integrity_text.insert("end",
                                f"    Atteso:  {p['expected'].get(algo, 'N/A')}\n")
                            self.integrity_text.insert("end",
                                f"    Attuale: {p['actual'].get(algo, 'N/A')}\n")
                    self.integrity_text.insert("end", "\n")
            
            # Salva risultato verifica
            verify_path = os.path.join(
                os.path.dirname(manifest_path),
                f"verify_result_{get_timestamp()}.json"
            )
            with open(verify_path, "w") as f:
                json.dump({
                    "timestamp": get_timestamp_full(),
                    "manifest": manifest_path,
                    "summary": summary,
                    "details": results,
                }, f, indent=2, ensure_ascii=False, default=str)
            
            self.log_message(f"[{'OK' if ok else 'ALERT'}] Verifica: {summary}")
            
            if ok:
                messagebox.showinfo("Verifica Integrità",
                                   f"✅ Integrità CONFERMATA\n\n"
                                   f"Tutti i {summary['total']} file sono integri.")
            else:
                messagebox.showwarning("Verifica Integrità",
                                      f"❌ Integrità COMPROMESSA\n\n"
                                      f"Alterati: {summary['failed']}\n"
                                      f"Mancanti: {summary['missing']}")
        
        self._run_in_thread(_verify)
    
    def cmd_analyze_processes(self):
        """Analizza processi da file syslog."""
        if not self._ensure_case_dir():
            return
        
        syslog_dir = os.path.join(self.current_case_dir, "syslog")
        if not os.path.exists(syslog_dir) or not os.listdir(syslog_dir):
            messagebox.showwarning("Attenzione",
                                   "Nessun file syslog trovato.\n"
                                   "Cattura prima il syslog dal tab 'SysLog/Crash'.")
            return
        
        # Usa l'ultimo syslog
        syslogs = sorted([f for f in os.listdir(syslog_dir) if f.endswith(".txt")])
        if not syslogs:
            messagebox.showwarning("Attenzione", "Nessun file syslog .txt trovato.")
            return
        
        syslog_path = os.path.join(syslog_dir, syslogs[-1])
        
        self.log_message(f"[ACTION] Analisi processi da: {syslogs[-1]}")
        self.integrity_text.delete("1.0", "end")
        self.integrity_text.insert("end", "Analisi processi in corso...\n")
        
        def _analyze():
            result = SyslogProcessParser.parse_syslog_file(syslog_path)
            
            if "error" in result:
                self.integrity_text.insert("end", f"\nErrore: {result['error']}\n")
                return
            
            self.integrity_text.delete("1.0", "end")
            header = f"{'═'*60}\n  PROCESSI iOS (da syslog)\n{'═'*60}\n\n"
            self.integrity_text.insert("end", header)
            self.integrity_text.insert("end", f"  Righe analizzate:    {result['total_lines']}\n")
            self.integrity_text.insert("end", f"  Processi unici:      {result['unique_processes']}\n\n")
            
            self.integrity_text.insert("end", f"  {'PROCESSO':<35} {'PID(s)':<15} {'MSG':>8}\n")
            self.integrity_text.insert("end", f"  {'-'*58}\n")
            
            sorted_procs = sorted(
                result["processes"].values(),
                key=lambda x: x["count"],
                reverse=True
            )
            
            for proc in sorted_procs:
                pids = ",".join(proc["pids"][:3])
                if len(proc["pids"]) > 3:
                    pids += f"+{len(proc['pids'])-3}"
                self.integrity_text.insert("end",
                    f"  {proc['name']:<35} {pids:<15} {proc['count']:>8}\n")
            
            # Salva report processi
            report_path = os.path.join(self.current_case_dir, "syslog",
                                        f"process_report_{get_timestamp()}.txt")
            SyslogProcessParser.generate_process_report(result, report_path)
            
            # Salva anche JSON
            json_path = report_path.replace(".txt", ".json")
            with open(json_path, "w") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            self._register_artifact("Report Processi (TXT)", report_path,
                                    f"{result['unique_processes']} processi estratti da syslog")
            self._register_artifact("Report Processi (JSON)", json_path,
                                    "Dati processi in formato JSON")
            
            self.log_message(f"[OK] Analisi processi: {result['unique_processes']} unici trovati")
        
        self._run_in_thread(_analyze)
    
    def cmd_generate_report(self, format_type="both"):
        """Genera report forense."""
        if not self._ensure_case_dir():
            return
        
        if not self._artifacts_list:
            messagebox.showwarning("Attenzione",
                                   "Nessun artefatto acquisito!\n"
                                   "Esegui prima delle acquisizioni.")
            return
        
        case_info = {
            "Numero Caso": self.var_case_number.get() or "N/A",
            "Descrizione": self.var_case_desc.get() or "N/A",
            "Data Acquisizione": get_timestamp_full(),
            "Directory Caso": self.current_case_dir,
        }
        
        examiner_info = {
            "Nome": self.var_examiner_name.get() or "N/A",
            "Organizzazione": self.var_examiner_org.get() or "N/A",
            "Note": self.var_examiner_note.get() or "",
        }
        
        device_info = {}
        if self.device.device_info:
            key_fields = [
                "DeviceName", "ProductType", "ProductVersion",
                "SerialNumber", "UniqueDeviceID", "WiFiAddress",
                "ActivationState", "BuildVersion",
            ]
            for k in key_fields:
                if k in self.device.device_info:
                    device_info[k] = self.device.device_info[k]
        
        if self.device.udid:
            device_info["UDID"] = self.device.udid
        
        report_gen = ForensicReportGenerator(
            case_info, examiner_info, device_info, self.acquisition_log
        )
        
        for art in self._artifacts_list:
            report_gen.add_artifact(
                art["name"], art["path"],
                art.get("hashes", {}),
                art.get("description", "")
            )
        
        ts = get_timestamp()
        reports_dir = os.path.join(self.current_case_dir, "reports")
        generated = []
        
        if format_type in ("txt", "both"):
            txt_path = os.path.join(reports_dir, f"forensic_report_{ts}.txt")
            report_gen.generate_txt(txt_path)
            generated.append(txt_path)
            self.log_message(f"[OK] Report TXT: {txt_path}")
        
        if format_type in ("html", "both"):
            html_path = os.path.join(reports_dir, f"forensic_report_{ts}.html")
            report_gen.generate_html(html_path)
            generated.append(html_path)
            self.log_message(f"[OK] Report HTML: {html_path}")
        
        msg = "Report generati:\n\n" + "\n".join(generated)
        messagebox.showinfo("Report Generato", msg)
    
    def run(self):
        """Avvia l'applicazione."""
        self.root.mainloop()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

def main():
    """Punto di ingresso principale."""
    # Verifica Python version
    if sys.version_info < (3, 7):
        print("ERRORE: Richiesto Python 3.7 o superiore")
        sys.exit(1)
    
    app = iOSForensicApp()
    app.run()


if __name__ == "__main__":
    main()
