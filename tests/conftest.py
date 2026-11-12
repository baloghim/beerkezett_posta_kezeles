import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
import fitz as pymupdf
from PySide2.QtWidgets import QApplication


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def pdf_bytes():
    doc = pymupdf.open()
    for number in range(3):
        page = doc.new_page()
        page.insert_text((60, 80), f'Teszt dokumentum {number + 1}')
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def folders(tmp_path):
    source, target = tmp_path / 'archívum', tmp_path / 'munkamappa'
    source.mkdir()
    target.mkdir()
    return source, target
