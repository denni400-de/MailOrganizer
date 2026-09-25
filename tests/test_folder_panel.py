from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from mailorganizer.ui.widgets.folder_panel import _build_tree, _detect_delimiter


def test_detect_delimiter_prefers_slash():
    assert _detect_delimiter(["INBOX", "INBOX/Archiv"]) == "/"


def test_detect_delimiter_falls_back_to_dot():
    assert _detect_delimiter(["INBOX", "INBOX.Work"]) == "."


def test_detect_delimiter_none_when_flat():
    assert _detect_delimiter(["INBOX", "Sent", "Trash"]) is None


@pytest.fixture
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_build_tree_nests_by_delimiter(qapp):
    from PyQt6.QtWidgets import QTreeWidget

    tree = QTreeWidget()
    _build_tree(tree, ["INBOX", "INBOX/Archiv", "INBOX/Archiv/2024"])

    assert tree.topLevelItemCount() == 1
    inbox = tree.topLevelItem(0)
    assert inbox.text(0) == "INBOX"
    assert inbox.childCount() == 1
    archiv = inbox.child(0)
    assert archiv.text(0) == "Archiv"
    assert archiv.childCount() == 1
    assert archiv.child(0).text(0) == "2024"


def test_build_tree_flat_when_no_delimiter(qapp):
    from PyQt6.QtWidgets import QTreeWidget

    tree = QTreeWidget()
    _build_tree(tree, ["INBOX", "Sent", "Trash"])

    assert tree.topLevelItemCount() == 3
    for i in range(3):
        assert tree.topLevelItem(i).childCount() == 0
