from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWidgets import QDialog
from .models import EDPDError


def print_pages(total, first=0, last=0, reverse=False):
    start, stop = (max(1, first), min(total, last)) if first and last else (1, total)
    result = list(range(start - 1, stop))
    return list(reversed(result)) if reverse else result


def print_pdf(pdf, parent):
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setDocName('EDPD dokumentum')
    dialog = QPrintDialog(printer, parent)
    dialog.setMinMax(1, pdf.pages)
    dialog.setOption(QPrintDialog.PrintDialogOption.PrintPageRange, True)
    dialog.setOption(QPrintDialog.PrintDialogOption.PrintSelection, False)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    render_to_printer(pdf, printer)


def render_to_printer(pdf, printer):
    """Teljes oldalak a nyomtató festhető téglalapjára; tesztelhető PDF-kimenettel."""
    pages = print_pages(pdf.pages, printer.fromPage(), printer.toPage(),
                        printer.pageOrder() == QPrinter.PageOrder.LastPageFirst)
    if not printer.supportsMultipleCopies() and printer.copyCount() > 1:
        copies = printer.copyCount()
        pages = pages * copies if printer.collateCopies() else [page for page in pages for _ in range(copies)]
    painter = QPainter()
    if not painter.begin(printer):
        raise EDPDError('A nyomtató nem indítható.')
    try:
        for index, page in enumerate(pages):
            if index and not printer.newPage():
                raise EDPDError('A nyomtatás megszakadt.')
            pix = pdf.render(page, 2.5)
            image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
            paper = printer.pageRect(QPrinter.Unit.DevicePixel)
            size = image.size().scaled(int(paper.width()), int(paper.height()), Qt.AspectRatioMode.KeepAspectRatio)
            bounds = QRectF(paper.x() + (paper.width() - size.width()) / 2,
                            paper.y() + (paper.height() - size.height()) / 2, size.width(), size.height())
            painter.drawImage(bounds, image)
    finally:
        painter.end()
