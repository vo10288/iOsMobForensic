# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  vo10288
"""Punto di ingresso per `python -m iosforensic`."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
