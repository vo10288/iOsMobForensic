# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  vo10288
"""Test del parser syslog e del rilevamento dei tipi di file nel backup."""

from __future__ import annotations

from iosforensic.backup import detect_type
from iosforensic.parsers import SyslogProcessParser

SYSLOG_SAMPLE = """\
Mar 12 10:15:00 iPhone SpringBoard(FrontBoard)[62] <Notice>: Application launched
Mar 12 10:15:01 iPhone SpringBoard(FrontBoard)[62] <Notice>: Scene did activate
Mar 12 10:15:02 iPhone locationd[85] <Notice>: Client registered
Mar 12 10:15:03 iPhone mediaserverd[97] <Error>: Audio route changed
riga malformata senza struttura
Mar 12 10:15:04 iPhone locationd[85] <Notice>: Position updated
"""


def _write_syslog(tmp_path):
    target = tmp_path / "syslog.txt"
    target.write_text(SYSLOG_SAMPLE, encoding="utf-8")
    return target


def test_parser_counts_processes(tmp_path):
    parser = SyslogProcessParser(_write_syslog(tmp_path))
    observations = parser.parse()
    names = [obs.name for obs in observations]

    assert "SpringBoard" in names
    assert "locationd" in names
    assert "mediaserverd" in names


def test_parser_sorts_by_occurrences(tmp_path):
    parser = SyslogProcessParser(_write_syslog(tmp_path))
    observations = parser.parse()

    # SpringBoard e locationd hanno 2 occorrenze, mediaserverd 1.
    assert observations[-1].name == "mediaserverd"
    assert observations[0].occurrences == 2


def test_parser_extracts_pids_and_levels(tmp_path):
    parser = SyslogProcessParser(_write_syslog(tmp_path))
    by_name = {obs.name: obs for obs in parser.parse()}

    assert by_name["locationd"].pids == (85,)
    assert by_name["mediaserverd"].levels == {"Error": 1}


def test_parser_skips_malformed_lines(tmp_path):
    parser = SyslogProcessParser(_write_syslog(tmp_path))
    parser.parse()

    assert parser.total_lines == 6
    assert parser.parsed_lines == 5


def test_parser_writes_report(tmp_path):
    parser = SyslogProcessParser(_write_syslog(tmp_path))
    report = parser.write_report(tmp_path / "out" / "processi.txt")
    content = report.read_text(encoding="utf-8")

    assert "SpringBoard" in content
    # L'avvertenza sul valore indiziario non deve mai sparire dal report.
    assert "AVVERTENZA" in content


def test_detect_type_recognises_signatures(tmp_path):
    cases = {
        "a.bin": (b"\xff\xd8\xff\xe0" + b"\x00" * 28, ".jpg"),
        "b.bin": (b"\x89PNG\r\n\x1a\n" + b"\x00" * 24, ".png"),
        "c.bin": (b"SQLite format 3\x00" + b"\x00" * 16, ".sqlite"),
        "d.bin": (b"bplist00" + b"\x00" * 24, ".plist"),
        "e.bin": (b"\x00\x00\x00\x18ftypheic" + b"\x00" * 16, ".heic"),
    }
    for name, (payload, expected) in cases.items():
        target = tmp_path / name
        target.write_bytes(payload)
        assert detect_type(target) == expected, name


def test_detect_type_returns_none_for_unknown(tmp_path):
    target = tmp_path / "ignoto.bin"
    target.write_bytes(b"\x01\x02\x03\x04" * 8)

    assert detect_type(target) is None


SYSLOG_WITH_SUBSYSTEM = """\
Mar 12 10:15:00 iPhone SpringBoard(FrontBoard)[62] <Notice>: prima
Mar 12 10:15:01 iPhone SpringBoard(FrontBoard)[62] <Notice>: seconda
"""


def test_subsystem_lines_are_not_counted_twice(tmp_path):
    """Regressione: la versione monolitica applicava due regex alla stessa riga.

    Una riga con sottosistema veniva contata sia dal pattern generico sia da
    quello del sottosistema, raddoppiando le occorrenze nel report.
    """
    target = tmp_path / "syslog.txt"
    target.write_text(SYSLOG_WITH_SUBSYSTEM, encoding="utf-8")

    observations = SyslogProcessParser(target).parse()

    assert len(observations) == 1
    assert observations[0].occurrences == 2  # due righe, non quattro


def test_parser_handles_lines_without_level(tmp_path):
    """idevicesyslog non emette <Level> per tutte le sorgenti."""
    target = tmp_path / "syslog.txt"
    target.write_text(
        "Mar 12 10:15:00 iPhone kernel[0]: messaggio senza livello\n", encoding="utf-8"
    )

    observations = SyslogProcessParser(target).parse()

    assert len(observations) == 1
    assert observations[0].name == "kernel"
