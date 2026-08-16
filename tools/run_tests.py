#!/usr/bin/env python3
from __future__ import annotations

import unittest

from _bootstrap import PROJECT_ROOT

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(PROJECT_ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
