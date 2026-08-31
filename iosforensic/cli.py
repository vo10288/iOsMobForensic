# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  vo10288
"""Interfaccia a riga di comando."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

from . import BANNER, __version__
from .backup import BackupAnalyzer
from .case import Case
from .device import DeviceError, DeviceInterface, ToolNotFoundError, check_environment
from .integrity import IntegrityVerifier
from .parsers import SyslogProcessParser
from .report import ForensicReportGenerator, human_size


def _progress(index: int, total: int, name: str) -> None:
    print(f"\r  [{index}/{total}] {name[:52]:<52}", end="", file=sys.stderr)
    if index == total:
        print(file=sys.stderr)


def _open_case(args) -> Case:
    return Case.load(Path(args.case_dir))


def _device(case: Case | None, udid: str | None) -> DeviceInterface:
    return DeviceInterface(udid=udid, logger=case.log if case else None)


# ---------------------------------------------------------------------- #
# Comandi
# ---------------------------------------------------------------------- #


def cmd_doctor(args) -> int:
    print(BANNER)
    print("Verifica delle dipendenze esterne:\n")
    missing_required = []
    for tool, info in check_environment().items():
        mark = "OK  " if info["available"] else ("MANCA" if info["required"] else "opz.")
        location = info["path"] or "non trovato"
        flag = "richiesto" if info["required"] else "opzionale"
        print(f"  [{mark:<5}] {tool:<22} {flag:<10} {location}")
        if info["required"] and not info["available"]:
            missing_required.append(tool)

    if missing_required:
        print(f"\nDipendenze obbligatorie mancanti: {', '.join(missing_required)}")
        print("Consulta la sezione 'Requisiti' del README per l'installazione.")
        return 1
    print("\nTutte le dipendenze obbligatorie sono presenti.")
    return 0


def cmd_devices(args) -> int:
    udids = DeviceInterface.list_devices()
    if not udids:
        print("Nessun dispositivo rilevato.")
        print("Verifica il cavo USB, sblocca il dispositivo e tocca 'Autorizza'.")
        return 1
    for udid in udids:
        device = DeviceInterface(udid=udid)
        paired = "sì" if device.is_paired() else "no"
        try:
            info = device.info()
            label = f"{info.get('DeviceName', '?')} — iOS {info.get('ProductVersion', '?')}"
        except (DeviceError, ToolNotFoundError):
            label = "(informazioni non disponibili: pairing necessario)"
        print(f"{udid}  pairing: {paired:<3}  {label}")
    return 0


def cmd_init(args) -> int:
    case = Case.create(
        case_number=args.case,
        examiner=args.examiner,
        notes=args.notes,
        organization=args.organization,
        root=Path(args.root) if args.root else None,
    )
    print(f"Caso creato: {case.path}")
    print("Usa questo percorso come --case-dir nei comandi successivi.")
    return 0


def cmd_info(args) -> int:
    case = _open_case(args)
    device = _device(case, args.udid)
    summary = device.summary()
    full = device.info()
    battery = device.battery()

    target_json = case.artifact("device_info", "device_info.json")
    target_json.write_text(
        json.dumps({**summary, **{f"battery.{k}": v for k, v in battery.items()}},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    target_txt = case.artifact("device_info", "device_info_full.txt")
    target_txt.write_text(
        "\n".join(f"{k}: {v}" for k, v in sorted(full.items())), encoding="utf-8"
    )

    for key, value in summary.items():
        print(f"{key:<22}: {value}")
    print(f"\nSalvato in {target_json.parent}")
    return 0


def cmd_apps(args) -> int:
    case = _open_case(args)
    device = _device(case, args.udid)
    apps = device.list_apps(scope=args.scope)
    target = case.artifact("app_list", f"apps_{args.scope}.txt")
    target.write_text(device.format_apps(apps), encoding="utf-8")
    case.artifact("app_list", f"apps_{args.scope}.json").write_text(
        json.dumps(apps, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"{len(apps)} applicazioni salvate in {target}")
    return 0


def cmd_backup(args) -> int:
    case = _open_case(args)
    device = _device(case, args.udid)

    if args.encrypted:
        password = getpass.getpass("Password di cifratura del backup: ")
        confirm = getpass.getpass("Conferma password: ")
        if password != confirm:
            print("Le password non coincidono.", file=sys.stderr)
            return 1
        print("ATTENZIONE: annota la password nel verbale. Senza di essa il")
        print("backup non è ripristinabile né analizzabile.")
        device.set_backup_encryption(True, password).check()

    print("Acquisizione del backup in corso. Non scollegare il dispositivo.")
    result = device.backup(case.dir("backup"))
    if not result.ok:
        print(f"\nBackup fallito: {result.stderr.strip()[:300]}", file=sys.stderr)
        return 1
    print("Backup completato.")
    return 0


def cmd_syslog(args) -> int:
    case = _open_case(args)
    device = _device(case, args.udid)
    target = case.artifact("syslog", "syslog.txt")
    print(f"Cattura del syslog per {args.duration} secondi...")
    device.syslog(target, duration=args.duration)

    parser = SyslogProcessParser(target)
    report = parser.write_report(case.artifact("syslog", "processi.txt"))
    print(f"Syslog salvato in {target}")
    print(f"Analisi processi in {report}")
    return 0


def cmd_crash(args) -> int:
    case = _open_case(args)
    device = _device(case, args.udid)
    result = device.crash_reports(case.dir("crash_reports"), keep_on_device=not args.purge)
    if not result.ok:
        print(f"Estrazione fallita: {result.stderr.strip()[:300]}", file=sys.stderr)
        return 1
    count = sum(1 for p in case.dir("crash_reports").rglob("*") if p.is_file())
    print(f"{count} crash report estratti in {case.dir('crash_reports')}")
    return 0


def cmd_provisioning(args) -> int:
    case = _open_case(args)
    device = _device(case, args.udid)
    result = device.provisioning_profiles(case.dir("provisioning_profiles"))
    print(f"{result['count']} profili estratti.")
    if not result["ok"]:
        print(f"Avviso: {result['error']}", file=sys.stderr)
    return 0


def cmd_afc(args) -> int:
    case = _open_case(args)
    device = _device(case, args.udid)
    mount_point = Path(args.mount_point)

    print(f"Mount AFC su {mount_point}...")
    device.mount_afc(mount_point, bundle_id=args.bundle_id).check()
    try:
        entries = device.scan_afc(mount_point, max_depth=args.depth)
        listing = case.artifact("afc_media", "afc_scan.json")
        listing.write_text(
            json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"{len(entries)} file rilevati, elenco in {listing}")

        if args.copy:
            categories = tuple(args.categories.split(",")) if args.categories else None
            copied, errors = device.copy_afc_files(
                mount_point, case.dir("afc_media"), categories=categories, progress=_progress
            )
            print(f"{copied} file copiati, {errors} errori")
    finally:
        # Il mount va sempre rilasciato: lasciarlo appeso blocca la
        # riconnessione del dispositivo e la cartella resta inaccessibile.
        device.unmount_afc(mount_point)
        print("AFC smontato.")
    return 0


def cmd_analyze(args) -> int:
    case = _open_case(args)
    analyzer = BackupAnalyzer(case.dir("backup"))
    stats = analyzer.analyze(progress=_progress)

    encrypted = {True: "sì", False: "no", None: "non determinabile"}[stats.encrypted]
    print(f"\nFile: {stats.file_count}  Totale: {human_size(stats.total_bytes)}")
    print(f"Backup cifrato: {encrypted}\n")
    for category, count in stats.by_category.most_common():
        print(f"  {category:<14} {count}")

    target = case.artifact("reports", "analisi_backup.json")
    analyzer.write_analysis(target)
    print(f"\nAnalisi salvata in {target}")

    if args.extract_media:
        if stats.encrypted:
            print("Backup cifrato: estrazione media non possibile senza decifratura.")
            return 0
        counters = analyzer.extract_media(case.dir("backup_media"), progress=_progress)
        for category, count in counters.items():
            print(f"  {category:<14} {count} file estratti")
    return 0


def cmd_hash(args) -> int:
    case = _open_case(args)
    entries = IntegrityVerifier(case).build(progress=_progress)
    total = sum(entry.size for entry in entries)
    print(f"Manifest creato: {len(entries)} file, {human_size(total)}")
    print(f"Salvato in {case.dir('hashes')}")
    return 0


def cmd_verify(args) -> int:
    case = _open_case(args)
    result = IntegrityVerifier(case).verify(progress=_progress)
    print(f"\n{result.summary()}")

    for label, items in (("ALTERATI", result.altered), ("MANCANTI", result.missing)):
        for item in items:
            print(f"  {label}: {item}")
    for item in result.added:
        print(f"  aggiunto dopo il manifest: {item}")

    if result.is_intact:
        print("\nIntegrità verificata: nessun artefatto alterato o mancante.")
        return 0
    print("\nVERIFICA FALLITA: sono state rilevate difformità.")
    return 2


def cmd_report(args) -> int:
    case = _open_case(args)
    html_path, txt_path = ForensicReportGenerator(case).generate()
    print(f"Report HTML: {html_path}")
    print(f"Report TXT : {txt_path}")
    return 0


def cmd_gui(args) -> int:
    try:
        from .gui.app import main as gui_main
    except ImportError as exc:
        print(f"Impossibile avviare la GUI: {exc}", file=sys.stderr)
        print("Su Debian/Ubuntu installa 'python3-tk'.", file=sys.stderr)
        return 1
    return gui_main()


# ---------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="iosforensic",
        description="Acquisizione forense logica di dispositivi iOS.",
        epilog="Distribuito sotto GPL-3.0-or-later, SENZA ALCUNA GARANZIA.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def with_case(sub):
        sub.add_argument("--case-dir", required=True, help="Cartella del caso")
        sub.add_argument("--udid", help="UDID del dispositivo (default: il primo collegato)")
        return sub

    subparsers.add_parser("doctor", help="Verifica le dipendenze esterne").set_defaults(
        func=cmd_doctor
    )
    subparsers.add_parser("devices", help="Elenca i dispositivi collegati").set_defaults(
        func=cmd_devices
    )
    subparsers.add_parser("gui", help="Avvia l'interfaccia grafica").set_defaults(func=cmd_gui)

    init = subparsers.add_parser("init", help="Crea un nuovo caso")
    init.add_argument("--case", required=True, help="Numero o identificativo del caso")
    init.add_argument("--examiner", required=True, help="Nome dell'esaminatore")
    init.add_argument("--organization", default="", help="Organizzazione o ente")
    init.add_argument("--notes", default="", help="Note iniziali")
    init.add_argument("--root", help="Cartella radice dei casi")
    init.set_defaults(func=cmd_init)

    info = with_case(subparsers.add_parser("info", help="Info del dispositivo"))
    info.set_defaults(func=cmd_info)

    apps = with_case(subparsers.add_parser("apps", help="Inventario delle applicazioni"))
    apps.add_argument("--scope", choices=("user", "system", "all"), default="user")
    apps.set_defaults(func=cmd_apps)

    backup = with_case(subparsers.add_parser("backup", help="Acquisisce il backup"))
    backup.add_argument("--encrypted", action="store_true", help="Attiva la cifratura del backup")
    backup.set_defaults(func=cmd_backup)

    syslog = with_case(subparsers.add_parser("syslog", help="Cattura il log di sistema"))
    syslog.add_argument("--duration", type=int, default=60, help="Durata in secondi")
    syslog.set_defaults(func=cmd_syslog)

    crash = with_case(subparsers.add_parser("crash", help="Estrae i crash report"))
    crash.add_argument(
        "--purge",
        action="store_true",
        help="Rimuove i report dal dispositivo dopo la copia (ALTERA IL REPERTO)",
    )
    crash.set_defaults(func=cmd_crash)

    prov = with_case(subparsers.add_parser("provisioning", help="Estrae i provisioning profile"))
    prov.set_defaults(func=cmd_provisioning)

    afc = with_case(subparsers.add_parser("afc", help="Monta e scansiona il filesystem media"))
    afc.add_argument("--mount-point", default="/tmp/ios_afc", help="Punto di mount")
    afc.add_argument("--bundle-id", help="Monta i Documents di una app specifica")
    afc.add_argument("--depth", type=int, default=3, help="Profondità di scansione")
    afc.add_argument("--copy", action="store_true", help="Copia i file nel caso")
    afc.add_argument(
        "--categories",
        help="Categorie da copiare, separate da virgola (images,videos,audio,documents)",
    )
    afc.set_defaults(func=cmd_afc)

    analyze = with_case(subparsers.add_parser("analyze", help="Analizza il backup acquisito"))
    analyze.add_argument("--extract-media", action="store_true", help="Estrae anche i media")
    analyze.set_defaults(func=cmd_analyze)

    with_case(subparsers.add_parser("hash", help="Crea il manifest degli hash")).set_defaults(
        func=cmd_hash
    )
    with_case(subparsers.add_parser("verify", help="Verifica l'integrità")).set_defaults(
        func=cmd_verify
    )
    with_case(subparsers.add_parser("report", help="Genera il report forense")).set_defaults(
        func=cmd_report
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ToolNotFoundError, DeviceError, FileNotFoundError, NotADirectoryError) as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrotto dall'utente.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
