import json
import pytest
from PySide2.QtCore import QEventLoop, QTimer
from PySide2.QtWidgets import QWidget, QTableWidget
from edpd import DISPLAY_NAME, __version__
from edpd.config import Settings, settings_path
from edpd.ui.about_dialog import AboutDialog
from edpd.ui.main_window import MainWindow
from edpd.ui.pdf_viewer import PDFViewer


def test_user_facing_name_and_only_main_toolbar_font_grows(app,folders):
    source,target=folders
    base=app.font().pointSizeF()
    table_base=QTableWidget().font().pointSizeF()
    window=MainWindow(Settings(source=str(source),target=str(target)),auto_refresh=False)
    window.show()
    app.processEvents()
    try:
        assert DISPLAY_NAME=='EDPD Menedzser'
        assert window.windowTitle()==f'EDPD Menedzser {__version__}'
        about=AboutDialog(window)
        assert 'EDPD Menedzser' in about.windowTitle()
        assert 'EDPD Menedzser' in about.info.toPlainText()
        assert 'EDPD – Postai dokumentumkezelő' not in about.info.toPlainText()
        about.reject()
        for action in window.actions:
            button=window.operation_toolbar.widgetForAction(action)
            assert button.font().pointSizeF()==pytest.approx(base+2)
        assert window.viewer.toolbar.font().pointSizeF()==pytest.approx(base)
        for action in window.viewer.toolbar.actions():
            if action.text():
                button=window.viewer.toolbar.widgetForAction(action)
                assert button.font().pointSizeF()==pytest.approx(base)
        assert window.docs_table.font().pointSizeF()==pytest.approx(table_base)
        # Reapplying a native style must not repeatedly add two points.
        from edpd.ui.appearance import apply_style
        apply_style(app.style().objectName())
        assert window.operation_toolbar.font().pointSizeF()==pytest.approx(base+2)
    finally:
        window.close()


@pytest.mark.parametrize('old_fields',[
    {'refresh_minutes':15,'history_days':14},
    {'refresh_minutes':30,'history_days':90,'qt_style':'Windows','icon_theme':'Nuvola',
     'geometry':'','panels':'','left_panels':''},
])
def test_old_profile_location_and_settings_remain_compatible(tmp_path,old_fields):
    path=settings_path()
    assert path.parts[-2:]==('EDPD','settings.json')
    path.parent.mkdir(parents=True)
    data={'source':str(tmp_path/'archive'),'target':str(tmp_path/'workspace'),**old_fields}
    path.write_text(json.dumps(data),encoding='utf-8')
    restored=Settings.load()
    assert restored.source==data['source'] and restored.target==data['target']
    assert restored.refresh_minutes==data['refresh_minutes']
    assert restored.icon_theme==old_fields.get('icon_theme','Crystal SVG')
    assert restored.qt_style==old_fields.get('qt_style','Fusion')
    restored.save()
    assert Settings.load()==restored and settings_path()==path


@pytest.mark.parametrize('mode',[None,'width','page'])
def test_every_page_action_resets_scroll_without_losing_view_state(app,pdf_bytes,mode):
    viewer=PDFViewer()
    viewer.resize(620,500)
    viewer.show()
    app.processEvents()
    viewer.open_data(pdf_bytes)
    if mode is None:
        viewer.zoom(2.0/viewer.scale)
    else:
        viewer.fit(mode)
    settle = QEventLoop()
    QTimer.singleShot(30, settle.quit)
    settle.exec_()  # Let fit-to-width settle after scrollbar visibility changes.
    actions={action.property('icon_role'):action for action in viewer.toolbar.actions() if action.text()}
    count=[]
    original_render=viewer.pdf.render
    def track(*args,**kwargs):
        count.append(1)
        return original_render(*args,**kwargs)
    viewer.pdf.render=track
    try:
        # All four toolbar paths, plus direct navigation and clamping at both ends.
        for role,expected in [('next',1),('last',2),('previous',1),('first',0)]:
            for bar in (viewer.scroll.horizontalScrollBar(),viewer.scroll.verticalScrollBar()):
                bar.setValue(bar.maximum())
            if mode is None:
                assert viewer.scroll.verticalScrollBar().value()>0
                assert viewer.scroll.horizontalScrollBar().value()>0
            previous_scale=viewer.scale
            actions[role].trigger()
            assert viewer.scroll.verticalScrollBar().value()==0
            app.processEvents()  # Check again after Qt's deferred scrollbar/layout updates.
            assert viewer.page==expected
            assert viewer.scroll.verticalScrollBar().value()==0
            assert viewer.scroll.horizontalScrollBar().value()==0
            assert viewer.fit_mode==mode
            assert viewer.scale==pytest.approx(previous_scale)
        for page,expected in [(1,1),(999,2),(-999,0)]:
            viewer.scroll.verticalScrollBar().setValue(viewer.scroll.verticalScrollBar().maximum())
            viewer.move(page)
            app.processEvents()
            assert viewer.page==expected and viewer.scroll.verticalScrollBar().value()==0
        assert len(count)<=9  # Seven navigations; reset must not itself re-render a page.
    finally:
        viewer.pdf.close()
        viewer.close()


def test_fit_buttons_use_the_same_visible_gap_as_print_and_save(app):
    viewer=PDFViewer()
    width=sum(viewer.toolbar.widgetForAction(a).sizeHint().width() for a in viewer.toolbar.actions())+128
    viewer.setMinimumWidth(width)
    viewer.resize(width,450)
    viewer.show()
    app.processEvents()
    try:
        widgets=[viewer.toolbar.widgetForAction(a) for a in
                 (viewer.width_action,viewer.page_action,viewer.print_action,viewer.save_action)]
        assert all(widget.isVisible() for widget in widgets)
        def gap(first,second):return second.geometry().left()-first.geometry().right()-1
        assert gap(widgets[0],widgets[1])==gap(widgets[2],widgets[3])
        assert gap(widgets[0],widgets[1])>=6
        spaces=viewer.toolbar.findChildren(QWidget,'pdf-group-space')
        assert len(spaces)==6 and all(space.width()==6 for space in spaces)
    finally:
        viewer.close()
