from __future__ import annotations

from PySide6.QtCore import QSettings

ORG_NAME = "MangaReaderTranslate"
APP_NAME = "MangaReaderTranslate"


def get_settings() -> QSettings:
    return QSettings(ORG_NAME, APP_NAME)
