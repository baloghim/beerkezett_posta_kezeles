import fitz
from PySide2.QtCore import QEventLoop, QTimer
from PySide2.QtWidgets import QStyle

from edpd.pdf_service import PDFService
from edpd.ui.pdf_viewer import PDFViewer


def test_fit_width_stays_stable_across_scrollbar_threshold(app, monkeypatch):
    rendered_pages = []
    original_render = PDFService.render

    def count_render(pdf, page, scale):
        rendered_pages.append(page)
        return original_render(pdf, page, scale)

    def settle():
        loop = QEventLoop()
        QTimer.singleShot(60, loop.quit)
        loop.exec_()
        assert not viewer.fit_timer.isActive()

    monkeypatch.setattr(PDFService, 'render', count_render)
    viewer = PDFViewer()
    viewer.resize(720, 520)
    viewer.show()
    app.processEvents()
    try:
        viewport = viewer.scroll.viewport()
        bar = viewer.scroll.verticalScrollBar()
        height = viewport.height()
        full_width = viewer.scroll.contentsRect().width()
        bar_width = bar.style().pixelMetric(QStyle.PM_ScrollBarExtent, None, bar)
        # Page two needs scrolling at full width but fits when the scrollbar
        # takes up space. The other pages sit on either side of that threshold.
        page_width = 600
        threshold = height * page_width / (full_width - 24 - bar_width / 2)
        with fitz.open() as doc:
            for page_height in (threshold - 30, threshold, threshold + 30):
                doc.new_page(width=page_width, height=page_height)
            viewer.open_data(doc.tobytes())

        settle()
        assert viewer.fit_mode == 'width'
        assert viewer.width_action.isChecked()
        initial_width = viewport.width()
        assert bar.maximum() == 0
        for page, scrollable in ((1, False), (2, True), (1, False), (0, False)):
            rendered_pages.clear()
            bar.setValue(bar.maximum())
            viewer.move(page)
            settle()
            assert rendered_pages == [page]
            assert viewport.width() == initial_width
            assert (bar.maximum() > 0) == scrollable
            assert bar.value() == 0

        rendered_pages.clear()
        viewer.resize(viewer.width() + 40, viewer.height())
        settle()
        assert viewport.width() > initial_width
        assert rendered_pages == [0]
        assert viewer.label.width() == viewport.width() - 24
    finally:
        viewer.clear()
        viewer.close()
