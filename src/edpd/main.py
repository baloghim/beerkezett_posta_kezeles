import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from .config import Settings
from .ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet('''
        QWidget { font-family: "Segoe UI", sans-serif; font-size: 13px; }
        QMainWindow, QDialog { background: #f5f7fa; }
        QToolBar { background: white; spacing: 8px; padding: 10px; border-bottom: 1px solid #dce3ec; }
        QToolButton, QPushButton { padding: 8px; }
        QTableWidget { background: white; alternate-background-color: #f2f6fa; border: 1px solid #dce3ec; }
        QHeaderView::section { background: #e6edf5; padding: 7px; border: none; }
        QStatusBar { color: #35506b; }
    ''')
    try:
        settings = Settings.load()
    except (OSError, ValueError, TypeError) as exc:
        QMessageBox.warning(None, 'Beállítások nem tölthetők be', f'{exc}\nAz alapértékekkel indulunk; ellenőrizze a Beállításokat!')
        settings = Settings()
    window = MainWindow(settings)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
