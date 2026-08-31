# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  vo10288
"""Test del manifest degli hash e della verifica di integrità.

È la parte del progetto che regge il valore probatorio degli artefatti:
se sbaglia, un file alterato passa per intatto. Va testata per prima.
"""

from __future__ import annotations

import hashlib

import pytest

from iosforensic.case import Case
from iosforensic.integrity import IntegrityVerifier, hash_file


@pytest.fixture()
def case(tmp_path):
    return Case.create(
        case_number="TEST-001",
        examiner="Esaminatore Test",
        root=tmp_path,
    )


def test_hash_file_matches_hashlib(tmp_path):
    payload = b"contenuto forense di prova" * 1000
    target = tmp_path / "artefatto.bin"
    target.write_bytes(payload)

    digests = hash_file(target)

    assert digests["md5"] == hashlib.md5(payload).hexdigest()
    assert digests["sha1"] == hashlib.sha1(payload).hexdigest()
    assert digests["sha256"] == hashlib.sha256(payload).hexdigest()


def test_hash_file_chunking_is_consistent(tmp_path):
    """Il digest non deve dipendere dalla dimensione del blocco di lettura."""
    target = tmp_path / "grande.bin"
    target.write_bytes(bytes(range(256)) * 5000)

    assert hash_file(target, chunk_size=64) == hash_file(target, chunk_size=1024 * 1024)


def test_case_structure_is_created(case):
    assert (case.path / "case.json").is_file()
    assert (case.path / "backup").is_dir()
    assert (case.path / "hashes").is_dir()


def test_manifest_covers_artifacts(case):
    case.artifact("device_info", "info.txt").write_text("UDID: 0000", encoding="utf-8")
    case.artifact("syslog", "syslog.txt").write_text("riga di log", encoding="utf-8")

    entries = IntegrityVerifier(case).build()
    paths = {entry.path for entry in entries}

    assert "device_info/info.txt" in paths
    assert "syslog/syslog.txt" in paths
    assert "case.json" in paths


def test_manifest_excludes_audit_log_and_itself(case):
    case.artifact("device_info", "info.txt").write_text("dati", encoding="utf-8")
    verifier = IntegrityVerifier(case)
    verifier.build()

    manifest = verifier.load_manifest()
    paths = {entry["path"] for entry in manifest["entries"]}

    # L'audit log cresce a ogni operazione: includerlo renderebbe il manifest
    # sempre difforme da sé stesso.
    assert "audit.log" not in paths
    assert not any(p.startswith("hashes/") for p in paths)


def test_verify_detects_intact_case(case):
    case.artifact("device_info", "info.txt").write_text("dati", encoding="utf-8")
    verifier = IntegrityVerifier(case)
    verifier.build()

    result = verifier.verify()

    assert result.is_intact
    assert result.altered == []
    assert result.missing == []


def test_verify_detects_alteration(case):
    target = case.artifact("device_info", "info.txt")
    target.write_text("originale", encoding="utf-8")
    verifier = IntegrityVerifier(case)
    verifier.build()

    target.write_text("manomesso", encoding="utf-8")
    result = verifier.verify()

    assert not result.is_intact
    assert "device_info/info.txt" in result.altered


def test_verify_detects_missing_file(case):
    target = case.artifact("device_info", "info.txt")
    target.write_text("dati", encoding="utf-8")
    verifier = IntegrityVerifier(case)
    verifier.build()

    target.unlink()
    result = verifier.verify()

    assert not result.is_intact
    assert "device_info/info.txt" in result.missing


def test_verify_reports_added_files_without_failing(case):
    case.artifact("device_info", "info.txt").write_text("dati", encoding="utf-8")
    verifier = IntegrityVerifier(case)
    verifier.build()

    case.artifact("screenshots", "nuovo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    result = verifier.verify()

    # Un artefatto acquisito dopo il manifest non invalida i precedenti.
    assert result.is_intact
    assert "screenshots/nuovo.png" in result.added


def test_verify_without_manifest_raises(case):
    with pytest.raises(FileNotFoundError):
        IntegrityVerifier(case).verify()


def test_audit_log_is_append_only(case):
    case.log("test.evento", "primo")
    case.log("test.evento", "secondo")

    entries = case.audit_entries()
    messages = [entry["message"] for entry in entries]

    assert "primo" in messages
    assert "secondo" in messages
    assert messages.index("primo") < messages.index("secondo")


def test_unreadable_file_does_not_produce_fake_hash(tmp_path, case):
    """Regressione: la versione monolitica catturava le eccezioni di lettura e

    scriveva la stringa "ERRORE: ..." al posto del digest. Lo stesso errore si
    ripresentava in verifica, quindi un file illeggibile risultava "integro".
    Ora l'errore si propaga e l'operatore lo vede.
    """
    import os
    import stat

    target = case.artifact("device_info", "protetto.bin")
    target.write_bytes(b"contenuto")
    os.chmod(target, 0o000)

    try:
        if os.access(target, os.R_OK):  # eseguito come root: test non applicabile
            pytest.skip("il test richiede un utente non privilegiato")
        with pytest.raises(OSError):
            hash_file(target)
    finally:
        os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)


def test_manifest_paths_are_relative_and_portable(case, tmp_path):
    """Il manifest deve restare valido se il caso viene spostato di disco.

    La versione monolitica salvava il percorso assoluto della directory nel
    manifest e lo usava in verifica: copiare il caso su un supporto di
    conservazione rendeva la verifica impossibile.
    """
    import shutil

    case.artifact("device_info", "info.txt").write_text("dati", encoding="utf-8")
    IntegrityVerifier(case).build()

    moved = tmp_path / "archivio" / case.path.name
    moved.parent.mkdir(parents=True)
    shutil.copytree(case.path, moved)

    result = IntegrityVerifier(Case.load(moved)).verify()

    assert result.is_intact
