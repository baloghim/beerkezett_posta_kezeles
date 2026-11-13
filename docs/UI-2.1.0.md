# EDPD 2.1.0 – felületi ellenőrzés

Ez a kezdeti Linux-ellenőrzés történeti feljegyzése. Az azóta elkészült,
közzétett Windows-kiadás eredményei: [EDPD 2.1.2](RELEASE-2.1.2.md).

Linux x64, Python 3.10.22, PySide2 5.15.2.1 / Qt 5.15.2, PyMuPDF 1.23.26.
Nem került be új futásidejű függőség; a Windows build továbbra is Python 3.10.11-et használ.

```bash
QT_QPA_PLATFORM=offscreen .venv-qt5/bin/python -m pytest -q
QT_QPA_PLATFORM=offscreen .venv-qt5/bin/python -m edpd.main --self-test --report /workspace/edpd-selftest.json
```

- Teljes tesztcsomag: 86 sikeres, 1 kihagyott (Windows Qt DLL-audit).
- Az új felületi tesztekből 9 sikeres: minden helyben elérhető stílus kiválasztása,
  mentése és alkalmazása; új folyamatban történő visszatöltés; hiányzó stílus
  Fusion-visszaállása; Mégse és sikertelen mentés; QSS-mentes felület;
  Névjegy elhelyezése és tartalma; feliratok; PDF-nézetváltás, újranyitás és méretezés.
- A 10 funkcionális önellenőrzés sikeres. A JSON külön felsorolja a ténylegesen
  kipróbált Qt-stílusokat: ezen a gépen Windows és Fusion.
- A teljes tesztcsomag továbbra is ellenőrzi az 1000 ZIP-es időszakszűrést,
  a munkamappa függetlenségét, a célzott törlést, a fájlzárakat.
- A próbák kizárólag szintetikus adatokat, helyi ideiglenes mappákat használnak.

A Windows csomagolási parancs ezen a Linux gépen a spec platformellenőrzésénél
leáll: „A kiadáshoz Windows x64 és Python 3.10 szükséges.” Windows EXE nem készült.
A GitHub API-kérés a környezeti proxynál 403 hibát kap; ez nem bizonyítja a
GitHub-fiók kiadási jogosultságának hiányát. Az `api.github.com` hálózati engedélye
tervezetként mentve, a tényleges hozzáférést a beállítás alkalmazása után újra kell vizsgálni.

A Windows-build és a Release elkészítéséhez a Windows workflow szükséges.
A csomagolt önellenőrzés már minden, a célgépen elérhető Qt-stílust is kipróbál.
A modern Windows runner eredménye nem helyettesíti a valódi Windows 10 1607,
SMB-megosztás és fizikai nyomtatás átvételi próbáját.
A README közvetlen letöltési linkje a meglévő 2.0.1 kiadáson maradt;
új link csak az új csomag tényleges közzététele és ellenőrzése után adható meg.
