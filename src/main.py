import os
import sys
from pathlib import Path

from filelock import FileLock, Timeout
from PySide6.QtCore import QStandardPaths, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle


def try_lock() -> FileLock:
    settings_folder = Path(
        QStandardPaths.writableLocation(QStandardPaths.GenericConfigLocation),
    ) / QGuiApplication.applicationName()

    if os.environ.get("MIRAGE_CONFIG_DIR"):
        settings_folder = Path(os.environ["MIRAGE_CONFIG_DIR"])

    lock = FileLock(settings_folder / ".lock", timeout=1)

    try:
        lock.acquire()
    except Timeout:
        print("Already running")
        sys.exit(1)

    return lock


def main():
    QGuiApplication.setOrganizationName("mirage")
    QGuiApplication.setApplicationName("mirage")
    QGuiApplication.setApplicationDisplayName("mirage")
    QGuiApplication.setApplicationVersion("0.7.1")

    lock = try_lock()

    QQuickStyle.setStyle("Fusion")
    QQuickStyle.setFallbackStyle("Default")

    app      = QGuiApplication(sys.argv)
    engine   = QQmlApplicationEngine()
    qml_file = Path("src/gui/Window.qml")

    engine.load(QUrl(str(qml_file)))

    if not engine.rootObjects():
        lock.release()
        sys.exit(-1)

    exit_code = app.exec()
    lock.release()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
