#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  vo10288
#
# Avvio con verifica preventiva delle dipendenze.

set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Errore: python3 non trovato." >&2
    exit 1
fi

# Verifica delle dipendenze esterne prima di aprire l'interfaccia: meglio
# scoprire ora che manca ifuse, non a dispositivo collegato.
python3 -m iosforensic doctor || {
    echo
    echo "Alcune dipendenze obbligatorie non sono installate."
    read -rp "Avviare comunque? [s/N] " answer
    [[ "${answer,,}" == "s" ]] || exit 1
}

exec python3 -m iosforensic "${@:-gui}"
