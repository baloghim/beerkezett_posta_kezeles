import hashlib
import json
from dataclasses import replace
from datetime import date
from zipfile import ZipFile

from PySide2.QtCore import Qt
from PySide2.QtGui import QIcon, QImage
from PySide2.QtTest import QTest

from edpd.config import Settings, ViewerSettings
from edpd.processed_store import ProcessedStore
from edpd.surface_styles import LUNA
from edpd.ui.icons import ASSETS, THEME_NAMES, icon, manager, set_theme
from edpd.ui.main_window import MainWindow
from edpd.ui.themes import manager as surface_manager
from test_ui import wait_for


def test_manager_default_and_existing_profiles(tmp_path):
    profile = tmp_path / 'settings.json'
    fresh = Settings.load(profile)
    assert (fresh.ui_style, fresh.surface_theme, fresh.icon_theme) == (LUNA, LUNA, 'SE98')
    viewer = ViewerSettings.load(profile)
    assert (viewer.ui_style, viewer.icon_theme) == ('Fusion', 'Crystal SVG')
    for fields, expected in [
        ({'qt_style': 'Windows'}, ('Windows', 'Crystal SVG')),
        ({'qt_style': ''}, ('Fusion', 'Crystal SVG')),
        ({'surface_theme': 'Longhorn Slate', 'icon_theme': 'Oxygen'}, ('Longhorn Slate', 'Oxygen')),
        ({'ui_style': 'Fusion', 'surface_theme': LUNA, 'icon_theme': 'Nuvola'}, ('Fusion', 'Nuvola')),
    ]:
        profile.write_text(json.dumps(fields), encoding='utf-8')
        before = profile.read_bytes()
        current = Settings.load(profile)
        assert (current.ui_style, current.icon_theme) == expected
        assert profile.read_bytes() == before


def test_all_themes_have_coloured_status_assets(app):
    previous = manager().name
    try:
        for name, record in manager().manifest['themes'].items():
            assert set(record['status_icons']) == {'processed', 'unprocessed'}
            set_theme(name)
            for role, info in record['status_icons'].items():
                directory = ASSETS / 'themes' / record['id']
                source = directory / 'original' / info['original']
                assert hashlib.sha256(source.read_bytes()).hexdigest() == info['sha256']
                assert info['license']
                assert not icon(role).isNull() and manager().sources[role] == name
                for size in (22, 40):
                    image = QImage(str(directory / str(size) / (role + '.png')))
                    assert image.width() == image.height() == size
                    pixels = [image.pixelColor(x, y) for y in range(size) for x in range(size)
                              if image.pixelColor(x, y).alpha() > 128]
                    assert len(pixels) > 10
                    if role == 'processed':
                        assert sum(c.green() > max(c.red(), c.blue()) + 20 for c in pixels) > 10
                    else:
                        assert all(max(c.red(), c.green(), c.blue()) - min(c.red(), c.green(), c.blue()) < 20
                                   for c in pixels)
    finally:
        set_theme(previous)


def test_status_cells_follow_snapshot_and_theme(app, folders, pdf_bytes):
    source, target = folders
    today = date.today()
    with ZipFile(source / f'{today:%Y%m%d}_test.zip', 'w') as archive:
        archive.writestr('sample.pdf', pdf_bytes)
    with ZipFile(source / '20200101_other.zip', 'w') as archive:
        archive.writestr('other.pdf', pdf_bytes)
    (target / 'sample.pdf').write_bytes(pdf_bytes)
    window = MainWindow(Settings(source=str(source), target=str(target), history_days=None), auto_refresh=False)
    window.split.setSizes([760, 840])
    window.show()
    try:
        snapshot = window.snapshot()
        window.apply_snapshot(snapshot)
        table = window.day_table
        table.apply_widths()
        app.processEvents()
        assert surface_manager().name == LUNA and manager().name == 'SE98'
        assert table.columnCount() == 5
        assert table.horizontalHeaderItem(4).text() == 'Feldolgozva'
        assert table.item(0, 2).textAlignment() == int(Qt.AlignCenter)
        assert table.item(0, 3).text() == 'Kicsomagolva'
        assert all(table.item(0, col).font().bold() for col in range(5))
        marker = table.item(0, 4)
        assert marker.text() == marker.toolTip() == '' and marker.icon().isNull()
        assert marker.data(Qt.UserRole) is None
        assert table.columnWidth(4) >= table.horizontalHeader().fontMetrics().horizontalAdvance('Feldolgozva')

        table.scrollToItem(marker)
        cell = table.visualItemRect(marker)
        QTest.mouseClick(table.viewport(), Qt.LeftButton, pos=cell.center())
        assert not ProcessedStore(source, target).read()
        window.mark_day(window.days[0])
        wait_for(app, lambda: not window.jobs)
        marker = table.item(0, 4)
        assert marker.toolTip() == 'Feldolgozva'
        assert table.item(0, 3).text() == 'Kicsomagolva' and table.item(0, 3).font().bold()
        before = marker.icon().cacheKey()
        for name in THEME_NAMES:
            set_theme(name)
            assert marker.icon().cacheKey() == icon('processed').cacheKey()
            assert marker.toolTip() == 'Feldolgozva'
            unmarked = table.item(1, 4)
            assert unmarked.icon().isNull() and unmarked.text() == unmarked.toolTip() == ''
            assert unmarked.data(Qt.UserRole) is None
        assert marker.icon().cacheKey() != before
        assert table.item(0, 2).textAlignment() == int(Qt.AlignCenter)

        # Compare the actually painted indicator with the same selected cell without its icon.
        table.scrollToItem(marker)
        app.processEvents()
        cell = table.visualItemRect(marker)
        indicator = marker.icon()
        painted = table.viewport().grab(cell).toImage()
        marker.setIcon(QIcon())
        blank = table.viewport().grab(cell).toImage()
        marker.setIcon(indicator)
        ink = [(x, y) for y in range(painted.height()) for x in range(painted.width())
               if painted.pixel(x, y) != blank.pixel(x, y)]
        assert ink
        for axis, extent in enumerate((painted.width(), painted.height())):
            low = min(point[axis] for point in ink)
            high = max(point[axis] for point in ink)
            assert abs(low + high - (extent - 1)) <= 4

        window.refresh()
        wait_for(app, lambda: not window.jobs)
        assert table.item(0, 4).toolTip() == 'Feldolgozva'
        window.mark_day(window.days[0])
        wait_for(app, lambda: not window.jobs)
        assert not ProcessedStore(source, target).read()
        marker = table.item(0, 4)
        assert marker.icon().isNull() and marker.text() == marker.toolTip() == ''
        assert marker.data(Qt.UserRole) is None
        assert table.item(0, 3).text() == 'Kicsomagolva' and table.item(0, 3).font().bold()
        app.processEvents()
        assert table.viewport().grab(table.visualItemRect(marker)).toImage() == blank

        window.apply_snapshot(replace(snapshot, mark_error='Tárolási hiba'))
        assert table.item(0, 4).icon().isNull()
        assert table.item(0, 4).toolTip() == 'Tárolási hiba'
        assert not window.processed_action.isEnabled()
        assert table.item(0, 3).font().bold()
    finally:
        window.close()
