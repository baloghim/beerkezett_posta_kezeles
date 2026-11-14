"""Capture the real Qt application with synthetic local ZIP/PDF fixtures only.

No reference/mockup image is read. The comparison only arranges actual captures.
"""
import os
import tempfile
import threading
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path
import argparse
import json
import fitz
from PySide2.QtCore import Qt, QRect, QTimer
from PySide2.QtGui import QImage, QPainter, QFont
from PySide2.QtWidgets import QApplication, QMessageBox
from edpd.config import Settings
from edpd.ui.appearance import apply_style
from edpd.ui.main_window import MainWindow
from edpd.ui.settings_dialog import SettingsDialog
from edpd.ui.themes import set_theme, THEME_NAMES
from edpd.ui.icons import set_theme as set_icons
from edpd.file_service import FileService


def wait(app, condition, timeout=15):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        app.processEvents()
        if condition():return
        time.sleep(.005)
    raise AssertionError('Synthetic GUI fixture did not settle')


def settle(app):
    deadline=time.monotonic()+.12
    while time.monotonic()<deadline:
        app.processEvents()
        time.sleep(.005)


def capture(output):
    app=QApplication.instance() or QApplication([])
    apply_style('Fusion','Alapértelmezett')
    output.mkdir(parents=True,exist_ok=True)
    previous={key:os.environ.get(key) for key in ('APPDATA','LOCALAPPDATA')}
    with tempfile.TemporaryDirectory(prefix='edpd-longhorn-') as directory:
        root=Path(directory)
        source,target=root/'szintetikus-archivum',root/'szintetikus-munkamappa'
        source.mkdir();target.mkdir()
        os.environ['APPDATA']=str(root/'profile');os.environ['LOCALAPPDATA']=str(root/'local-profile')
        font_path=next((p for p in (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
                      Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/arial.ttf') if p.is_file()),None)
        font_name='EDPDTest' if font_path else 'helv'
        doc=fitz.open()
        for index in range(3):
            page=doc.new_page()
            if font_path:page.insert_font(fontname=font_name,fontfile=str(font_path))
            page.insert_text((52,82),'Mesterséges tesztdokumentum',fontsize=24,fontname=font_name)
            page.insert_text((52,125),'EDPD Menedzser – felületi ellenőrzés',fontsize=13,fontname=font_name)
            page.draw_line((52,142),(540,142),color=(.3,.4,.5))
            page.insert_textbox(fitz.Rect(52,172,535,320),
                'Ez a PDF kizárólag az alkalmazás megjelenésének ellenőrzésére készült.\n'
                'Nem tartalmaz valódi hivatali dokumentumot vagy személyes adatot.\n\n'
                'A lapozás, a nagyítás, az eredeti színek és a fehér lap megmaradnak.',fontsize=12,fontname=font_name)
            for x,colour in [(52,(.85,.15,.12)),(155,(.12,.55,.25)),(258,(.15,.35,.85))]:
                page.draw_rect(fitz.Rect(x,360,x+76,391),color=colour,fill=colour)
            page.insert_text((52,440),f'{index+1}. oldal / 3',fontsize=12,fontname=font_name)
        data=doc.tobytes();doc.close()
        names_by_offset=[['Küldemény_001.pdf','Küldemény_002.pdf'],['Értesítő_015.pdf'],['Jegyzőkönyv_004.pdf']]
        for offset,names in enumerate(names_by_offset):
            when=date.today()-timedelta(days=offset)
            with zipfile.ZipFile(source/f'{when:%Y%m%d}_TESZT.zip','w') as archive:
                for name in names:archive.writestr(name,data)
        bad=source/f'{date.today()-timedelta(days=3):%Y%m%d}_HIBAS_TESZT.zip'
        bad.write_bytes(b'Intentional invalid synthetic archive')
        for name in ('Küldemény_001.pdf','Értesítő_015.pdf','Egyéb_dokumentum.pdf'):
            (target/name).write_bytes(data)
        window=MainWindow(Settings(source=str(source),target=str(target)))
        window.resize(1600,900)
        window.show()
        try:
            wait(app,lambda:len(window.days)==4 and not window.jobs)
            window.mark_day(window.days[1])
            wait(app,lambda:not window.jobs)
            window.docs_table.selectRow(window.work_keys.index('küldemény_001.pdf'))
            wait(app,lambda:window.viewer.pdf is not None and not window.jobs)
            window.day_table.selectRow(1)
            def save(name,widget=window):
                settle(app)
                path=output/name
                assert widget.grab().save(str(path)),str(path)
            shots=[]
            for filename,surface,icons in [
                ('longhorn-default.png','Alapértelmezett','Crystal SVG'),
                ('longhorn-blue-crystal.png','Longhorn Blue','Crystal SVG'),
                ('longhorn-blue-nuvola.png','Longhorn Blue','Nuvola'),
                ('longhorn-slate-crystal.png','Longhorn Slate','Crystal SVG')]:
                set_theme(surface);set_icons(icons);save(filename);shots.append((filename,surface+' / '+icons))
            set_theme('Longhorn Blue');set_icons('Crystal SVG')
            settings=SettingsDialog(Settings(source=str(source),target=str(target),surface_theme='Longhorn Blue'),window)
            settings.show();save('longhorn-blue-settings.png',settings);settings.reject()
            # Exercise the real transaction, pausing only the synthetic progress callback.
            bad.unlink();window.refresh();wait(app,lambda:not window.jobs)
            window.day_table.selectRow(0)
            gate,entered=threading.Event(),threading.Event()
            original=FileService.extract
            def extract(service,*args,**kwargs):
                notify=kwargs['progress']
                def progress(text,done,total):
                    notify(text,done,total)
                    if total and done and not entered.is_set():
                        entered.set()
                        if not gate.wait(15):raise TimeoutError('Synthetic capture gate expired')
                kwargs['progress']=progress
                return original(service,*args,**kwargs)
            FileService.extract=extract
            answer=QTimer()
            def confirm_synthetic_extraction():
                modal=app.activeModalWidget()
                if isinstance(modal,QMessageBox):
                    for button in modal.buttons():
                        if button.text().startswith('Meglévők kihagyása'):
                            button.click()
                            return
            answer.timeout.connect(confirm_synthetic_extraction)
            answer.start(10)
            try:
                window.extract()
                wait(app,lambda:entered.is_set() and window.extraction_dialog is not None and window.extraction_dialog.isVisible())
                save('longhorn-blue-extraction.png',window.extraction_dialog)
            finally:
                gate.set();answer.stop();FileService.extract=original
            wait(app,lambda:not window.jobs and not window.extracting)
            # Viewport sweep keeps real data and records native toolbar overflow.
            sweep=[]
            for width,height in ((1280,720),(1600,900),(1920,1080)):
                window.resize(width,height);settle(app)
                actions=(window.viewer.width_action,window.viewer.page_action,window.viewer.print_action,window.viewer.save_action)
                sweep.append({'requested':[width,height],'actual':[window.width(),window.height()],
                              'splitters':[window.split.count(),window.left.count()],
                              'pdf_labels':[action.text() for action in actions],
                              'pdf_buttons_visible':[window.viewer.toolbar.widgetForAction(action).isVisible() for action in actions]})
            result={'platform':os.name,'qt_platform':app.platformName(),'synthetic_data_only':True,'viewports':sweep}
            (output/'longhorn-visual-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            canvas=QImage(2560,1520,QImage.Format_RGB32);canvas.fill(Qt.white)
            painter=QPainter(canvas);painter.setFont(QFont(app.font().family(),16,QFont.Bold))
            for i,(filename,label) in enumerate(shots):
                x,y=(i%2)*1280,(i//2)*760
                painter.setPen(Qt.black);painter.drawText(QRect(x+14,y,1250,40),Qt.AlignVCenter,label)
                image=QImage(str(output/filename)).scaled(1280,720,Qt.IgnoreAspectRatio,Qt.SmoothTransformation)
                painter.drawImage(x,y+40,image)
            painter.end();assert canvas.save(str(output/'longhorn-theme-comparison.png'))
            return result
        finally:
            set_theme('Alapértelmezett');set_icons('Crystal SVG')
            window.close()
            for key,value in previous.items():
                if value is None:os.environ.pop(key,None)
                else:os.environ[key]=value


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('docs'))
    args=parser.parse_args();print(json.dumps(capture(args.output),ensure_ascii=False))
