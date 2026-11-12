"""Qt 5 saját tulajdonú képpuffer: nincs Shiboken által kölcsönzött Python-memória."""
from PySide2.QtGui import QImage
from .models import EDPDError


def image_from_pixmap(pixmap):
    # A bytes/stride QImage-konstruktor PySide2 alatt túlterhelés- és
    # élettartam-problémás. A beépített PPM-dekóder önálló Qt-képet készít.
    image = QImage.fromData(pixmap.tobytes('ppm'), 'PPM')
    if image.isNull():
        raise EDPDError('A PDF-oldal képe nem hozható létre.')
    return image
