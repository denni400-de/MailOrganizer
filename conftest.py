"""Ensures Qt widget tests run headlessly by default (no display required), so `pytest`
works out of the box on CI and on machines without a graphical session. Override by
exporting QT_QPA_PLATFORM yourself before running tests (e.g. to watch them visually).
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
