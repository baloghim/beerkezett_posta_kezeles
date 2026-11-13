import sys
import time


def main():
    started = time.perf_counter_ns()
    import argparse
    parser = argparse.ArgumentParser(description='EDPD – Postai dokumentumkezelő')
    parser.add_argument('--self-test', action='store_true', help='Izolált indítási és működési próba')
    parser.add_argument('--report', help='Az önellenőrzés JSON-eredménye')
    parser.add_argument('--require-windows1607', action='store_true')
    parser.add_argument('--recover-extraction', help='Megőrzött .edpd-recovery-* mappa helyreállítása')
    parser.add_argument('--startup-report', help='Csak időadatokat tartalmazó indítási jelentés')
    parser.add_argument('--startup-exit-ms', type=int, default=0, help='Izolált indítási mérés automatikus bezárása')
    parser.add_argument('--startup-test-namespace', default='')
    parser.add_argument('--startup-delay-ms', type=int, default=0)
    parser.add_argument('--startup-network-delay-ms', type=int, default=0)
    args = parser.parse_args()
    probing = bool(args.startup_report and args.startup_exit_ms > 0)
    if (args.startup_test_namespace or args.startup_delay_ms or args.startup_network_delay_ms) and not probing:
        parser.error('A tesztparaméterekhez startup-report és startup-exit-ms szükséges.')
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
    from .startup_trace import StartupTrace
    trace = StartupTrace(started, args.startup_report)
    trace.network_delay_ms = max(0, args.startup_network_delay_ms)
    from .single_instance import InstanceGuard
    guard = InstanceGuard(args.startup_test_namespace or 'manager-v1')
    try:
        before = time.perf_counter()
        if not guard.acquire():
            peer = guard.notify_existing(show_notice=not probing)
            trace.add('instance_check_ms', (time.perf_counter() - before) * 1000)
            if trace.report:
                trace.publish('secondary', **peer)
            return 0
        trace.add('instance_check_ms', (time.perf_counter() - before) * 1000)
        if probing:
            trace.publish('initializing')
        if args.startup_delay_ms:
            time.sleep(max(0, args.startup_delay_ms) / 1000)
        before = time.perf_counter()
        from PySide2.QtCore import Qt, QTimer
        trace.add('qt_core_import_ms', (time.perf_counter() - before) * 1000)
        before = time.perf_counter()
        from PySide2.QtWidgets import QApplication, QSplashScreen, QMessageBox
        from PySide2.QtGui import QPixmap, QPainter, QColor, QFont
        app = QApplication(sys.argv)
        trace.add('qt_widgets_application_ms', (time.perf_counter() - before) * 1000)
        before = time.perf_counter()
        from .ui.icons import icon, set_theme
        app.setWindowIcon(icon('app'))
        trace.add('icon_resources_load_ms', (time.perf_counter() - before) * 1000)
        pixmap = QPixmap(480, 180)
        pixmap.fill(QColor('white'))
        painter = QPainter(pixmap)
        painter.drawPixmap(208, 12, icon('app').pixmap(64, 64))
        painter.setPen(QColor('black'))
        painter.setFont(QFont(app.font().family(), 14, QFont.Bold))
        painter.drawText(10, 85, 460, 35, Qt.AlignCenter, 'EDPD – Postai dokumentumkezelő')
        painter.setFont(QFont(app.font().family(), 11))
        painter.drawText(10, 125, 460, 30, Qt.AlignCenter, 'A program indítása…')
        painter.end()
        splash = QSplashScreen(pixmap)
        guard.tag_window(splash, 'splash')
        splash.show()
        app.processEvents()
        trace.add('splash_creation_ms', (time.perf_counter() - before) * 1000)
        trace.mark('splash_visible')
        before = time.perf_counter()
        from .config import Settings
        configuration_error = None
        try:
            settings = Settings.load()
        except (OSError, ValueError, TypeError) as exc:
            configuration_error = type(exc).__name__
            settings = Settings()
        trace.add('settings_load_ms', (time.perf_counter() - before) * 1000)
        before = time.perf_counter()
        from .ui.appearance import apply_style
        apply_style(settings.qt_style)
        set_theme(settings.icon_theme)
        trace.add('appearance_setup_ms', (time.perf_counter() - before) * 1000)
        before = time.perf_counter()
        from .ui.main_window import MainWindow
        trace.add('main_modules_pdf_print_import_ms', (time.perf_counter() - before) * 1000)
        before = time.perf_counter()
        window = MainWindow(settings, startup_trace=trace, auto_refresh=False)
        trace.add('main_window_construction_ms', (time.perf_counter() - before) * 1000)
        guard.tag_window(window)
        window.show()
        splash.finish(window)
        trace.mark('main_window_visible')
        trace.publish('visible', configuration_error=configuration_error, icon_theme=settings.icon_theme)
        activation_timer = QTimer(window)
        activation_timer.timeout.connect(lambda: guard.poll_activation(window))
        activation_timer.start(100)
        if hasattr(window, 'refresh'):
            QTimer.singleShot(0, window.refresh)
        if configuration_error and not probing:
            QTimer.singleShot(0, lambda: QMessageBox.warning(window, 'Beállítások nem tölthetők be',
                'A beállításfájl nem olvasható vagy hibás. Az alapértékekkel indultunk; ellenőrizze a Beállításokat!'))
        if probing:
            def finish_probe():
                if getattr(window, 'jobs', None):
                    QTimer.singleShot(25, finish_probe)
                else:
                    window.close()
            QTimer.singleShot(args.startup_exit_ms, finish_probe)
        return app.exec_()
    finally:
        guard.close()


if __name__ == '__main__':
    sys.exit(main())
