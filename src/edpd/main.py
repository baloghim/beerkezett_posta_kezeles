import sys


def main():
    import argparse
    parser = argparse.ArgumentParser(description='EDPD – Postai dokumentumkezelő')
    parser.add_argument('--self-test', action='store_true', help='Izolált indítási és működési próba')
    parser.add_argument('--report', help='Az önellenőrzés JSON-eredménye')
    parser.add_argument('--require-windows1607', action='store_true')
    parser.add_argument('--recover-extraction', help='Megőrzött .edpd-recovery-* mappa helyreállítása')
    args = parser.parse_args()
    if args.recover_extraction:
        if args.self_test or args.report or args.require_windows1607:
            parser.error('A helyreállítás külön művelet.')
        from .extraction_transaction import recover
        from PySide2.QtWidgets import QApplication, QMessageBox
        app = QApplication([])
        try:
            from .config import Settings
            settings = Settings.load()
            recover(args.recover_extraction, settings.source, settings.target)
        except Exception as exc:
            QMessageBox.warning(None, 'Helyreállítás nem teljes', str(exc))
            sys.exit(1)
        QMessageBox.information(None, 'Helyreállítás', 'A helyreállítás sikeres.')
        sys.exit(0)
    if args.self_test:
        if not args.report:
            parser.error('Az önellenőrzéshez --report útvonal szükséges.')
        from .self_test import run
        sys.exit(run(args.report, args.require_windows1607))
    if args.report or args.require_windows1607:
        parser.error('Ezek a kapcsolók csak --self-test mellett használhatók.')
    from PySide2.QtWidgets import QApplication, QMessageBox
    from .config import Settings
    from .ui.main_window import MainWindow
    app = QApplication(sys.argv)
    from .ui.icons import icon
    app.setWindowIcon(icon('app'))
    try:
        settings = Settings.load()
    except (OSError, ValueError, TypeError) as exc:
        QMessageBox.warning(None, 'Beállítások nem tölthetők be', f'{exc}\nAz alapértékekkel indulunk; ellenőrizze a Beállításokat!')
        settings = Settings()
    from .ui.appearance import apply_style
    apply_style(settings.qt_style)
    window = MainWindow(settings)
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
