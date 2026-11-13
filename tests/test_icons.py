import json
import struct
from PySide2.QtGui import QImage
from edpd.ui.icons import ASSETS, icon
from edpd.ui.pdf_viewer import PDFViewer
from edpd.ui.about_dialog import AboutDialog


def test_every_bundled_crystal_icon_decodes_and_renders(app):
    metadata=json.loads((ASSETS/'manifest.json').read_text())
    assert metadata['commit']=='f8863b558b8eedf22caea0eabe18030bfcbe0783'
    for name,entry in metadata['icons'].items():
        for size in entry['sizes']:
            assert not QImage(str(ASSETS/'original'/str(size)/(name+'.png'))).isNull()
        for size in (22,32,48,64,128,256):
            assert not icon(name).pixmap(size,size).isNull(),(name,size)
    assert not icon('app').pixmap(256,256).isNull()
    assert (ASSETS/'icons/22/width.png').read_bytes()!=(ASSETS/'icons/22/page.png').read_bytes()


def test_pdf_toolbar_has_nine_real_icons_and_smaller_size(app):
    viewer=PDFViewer();actions=[a for a in viewer.toolbar.actions() if a.text()]
    assert len(actions)==9
    assert {a.text() for a in actions}=={'Első oldal','Előző oldal','Következő oldal','Utolsó oldal','Nagyítás','Kicsinyítés','Szélesség','Teljes oldal','Nyomtatás'}
    for action in actions:
        assert not action.icon().pixmap(22,22).isNull()
        assert action.toolTip()
    assert viewer.toolbar.iconSize().width()==22
    viewer.close()


def test_ico_contains_all_seven_valid_frames_and_about_image(app):
    data=(ASSETS/'edpd.ico').read_bytes()
    assert struct.unpack_from('<HHH',data)==(0,1,7)
    sizes=[]
    for i in range(7):
        w,h,_,_,_,_,n,offset=struct.unpack_from('<BBBBHHII',data,6+16*i)
        image=QImage.fromData(data[offset:offset+n]);sizes.append(w or 256)
        assert image.width()==(w or 256) and image.height()==(h or 256)
    assert sizes==[16,24,32,48,64,128,256]
    dialog=AboutDialog()
    assert not dialog.app_icon.pixmap().isNull()
    assert 'Everaldo Coelho' in dialog.info.toPlainText()
    assert 'Viet Dang' in dialog.info.toPlainText() and 'LGPL' in dialog.info.toPlainText()
    dialog.reject()
