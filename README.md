# EDPD – Postai dokumentumkezelő

Magyar nyelvű, helyben futó Windows-alkalmazás a Magyar Posta napi EDPD ZIP-csomagjainak áttekintéséhez, a PDF-ek megtekintéséhez, nyomtatásához és az ideiglenes munkamappa kezeléséhez. Nem iktatórendszer. Nincs szerver, adatbázis, telemetria vagy dokumentumfeltöltés.

## Windows letöltés

**Még nincs ellenőrzött, közzétett Windows-kiadás, ezért letöltési hivatkozás sem szerepel itt.**

A [Windows kiadás munkafolyamat](https://github.com/baloghim/beerkezett_posta_kezeles/actions/workflows/windows-build.yml) sikeres futásának **Artifacts** részében az `EDPD-Manager-Windows-x64` csomag tölthető le. Artifact csak sikeres build után létezik; letöltéséhez GitHub-bejelentkezés szükséges lehet. A `v*` verziócímkével indított sikeres futás verziózott GitHub Release-t és ZIP-mellékletet is létrehoz.

## Funkciók

- Dátummal kezdődő ZIP-ek csoportosítása nap szerint, a legújabb nappal elöl; ZIP-tartalomjegyzék gyorsítótárazása.
- Három mozgatható panel: napi csomagok, dokumentumlista, PDF-betekintő.
- Kizárólag PDF-ek, a belső ZIP-mappaútvonalak és CSV-k kihagyásával.
- ZIP-ből vagy a munkamappából megtekintés, lapozás, nagyítás, szélességhez és ablakhoz igazítás.
- Natív Qt/Windows nyomtatási párbeszéd: teljes PDF-oldalak renderelése, oldalintervallum és nyomtatóbeállítások.
- Teljes napi kicsomagolás, meglévők kihagyása vagy külön választott felülírás.
- Megerősített napi törlés és a munkamappa közvetlen PDF-jeinek ürítése.
- Valós mappatartalomból számított státusz, közös operációsrendszer-szintű fájlzár, háttérben futó hálózati műveletek.
- Helyi felhasználói beállítások és 5–60 perces automatikus frissítés, 15 perces alapértékkel.

![EDPD felület szintetikus tesztadatokkal](docs/screenshot.png)

## Rendszerkövetelmények és indítás

Windows 10/11 x64; ajánlott Full HD képernyő, olvasási jogosultság a forráshoz, írási/törlési és hálózati zárolási jogosultság a munkamappához. A teljes kiadási ZIP-et egy helyi mappába kell kibontani, majd az `EDPD-Manager.exe` indítható. A mellette található `_internal` mappát is meg kell tartani. A kiadás használatához nem kell Python.

## Mappák beállítása

Indításkor a **Beállítások** gombbal adja meg a saját gépén elérhető útvonalakat. Meghajtóbetűjel és UNC-útvonal egyaránt használható. Alapértékek:

- Forrás: `H:\PostaEDPB\10_Komárom-Esztergom megye`
- Cél: `G:\Igazgatas\DMS_One\00_t_meghajtóról érkezők`

A program nem hozza létre ezeket a hálózati mappákat. A forrás kizárólag olvasható; a cél nem lehet vele azonos, alárendelt vagy fölérendelt mappa. Mentéskor ellenőrizzük az elérhetőséget és a cél írási jogosultságát. Elérhetetlenség esetén módosítsa az útvonalat, vagy használja a **Frissítés** gombot.

A beállításfájl `%APPDATA%\EDPD\settings.json`. Az ablak és panelek elrendezése bezáráskor megmarad. A helyi beállítások nem kerülnek a megosztásra.

## Napi munkafolyamat

1. Válasszon egy napot. Az alsó lista csak az adott napi ZIP-ek PDF-jeit mutatja.
2. Dokumentumra kattintva megjelenik a PDF; ez nem csomagol ki a munkamappába. Ha ugyanilyen nevű PDF már ott van, a program azt nyitja meg.
3. A **Kicsomagolás** az egész nap összes PDF-jét közvetlenül a célba helyezi. Válassza a **Meglévők kihagyása** vagy **Meglévők felülírása** lehetőséget. A **Mégse** nem végez műveletet.
4. A **Nyomtatás** az éppen megnyitott teljes PDF-hez nyit párbeszédet. A lapozógombok csak a megtekintést befolyásolják.
5. A **Napi adag törlése** kizárólag a kiválasztott naphoz tartozó PDF-eket törli a célból, megerősítés után. Több naphoz tartozó fájlnévnél leáll.
6. A **Munkamappa ürítése** minden közvetlenül ott található PDF-et töröl, megerősítés után; egyéb fájlt és almappát nem érint.

Nincs feldolgozási napló: a „Nincs kicsomagolva”, „Részben kicsomagolva” és „Kicsomagolva” állapot mindig a pillanatnyi célmappán alapul. Hibás csomag és méreteltérés külön jelzést kap. Több ZIP-en belüli azonos lapos fájlnév esetén az adott nap nem csomagolható ki.

## Többfelhasználós működés és biztonság

Minden kliens a célban lévő `.edpd-operation.lock` technikai fájl ugyanazon bájtját zárolja. Windows alatt Windows fájlzárat használunk, amelyet az SMB-kiszolgáló közvetít. A zárfájlt nem szabad törölni; nem állapotnapló. A fájl megléte nem jelent foglaltságot. Folyamatkilépéskor az OS oldja a zárat. Minden módosító művelet a zár megszerzése után ismét ellenőrzi az állapotot.

A normál másolás ellenőrzött ZIP-olvasásból ideiglenes fájlba, majd atomikus átnevezéssel/cserével történik. Egy napi művelet több fájlból áll: hálózati hiba esetén a már sikeresen elkészült fájlok megmaradnak. Frissítés után a hiányzók kicsomagolása biztonságosan újraindítható. Az alapértelmezett kihagyás soha nem ír felül.

A későbbi Viewer kiadáshoz a `Capabilities` programlogikai szinten is tiltani tudja a felülírást és törlést; ebben a projektben csak a Manager indulóprogram és build készül.

A működési határokat, a megszakadt műveletek kezelését és a szükséges valós Windows/SMB/nyomtatási átvételi próbákat a [Windows-ellenőrzési útmutató](docs/WINDOWS-VALIDATION.md) tartalmazza. Éles üzem előtt ezeket el kell végezni.

## Fejlesztői telepítés

Python 3.12 vagy újabb kompatibilis verzió szükséges. Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m edpd.main
```

Linuxon ugyanez `.venv/bin/python` útvonallal futtatható. Meglévő izolált checkoutban dolgozzon; új Git worktree nem szükséges. A PySide6 és PyMuPDF verziója rögzített a projektleírásban.

## Tesztek futtatása

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.venv\Scripts\python -m pytest -q
```

Linuxon: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`.

A tesztek kizárólag ideiglenes, szintetikus adatokkal dolgoznak. Valós NEAK hálózati útvonalat nem használnak. A felületpróba, PDF-renderelés és nyomtatási oldalintervallum ellenőrzése nem helyettesíti a fizikai Windows-nyomtatási próbát.

## Windows EXE készítése

Windows környezetben, telepített fejlesztői függőségekkel:

```powershell
.venv\Scripts\python -m PyInstaller --noconfirm --clean --windowed --onedir --name EDPD-Manager --paths src --collect-all pymupdf run_edpd.py
Compress-Archive -Path dist/EDPD-Manager -DestinationPath EDPD-Manager-Windows-x64.zip
```

A PyInstaller Qt-hookjai gyűjtik a PySide6 modulokat és platformpluginokat. A GitHub Actions Windows runneren telepít, tesztel, csomagol és feltölti az artifactot. Verziózott kiadáshoz `v0.1.0` jellegű címke szükséges. Kiadás előtt a verziószámot a `pyproject.toml` és `src/edpd/__init__.py` fájlokban együtt kell módosítani.

## Verzió és licencek

Fejlesztői verzió: **0.1.0**. Ellenőrzött éles Windows-kiadás még nincs.

A projekt saját kódjára nincs megadva felhasználási licenc; ennek kiválasztása a jogtulajdonos feladata. A PySide6 és a PyMuPDF külön licencei érvényesek. A PyMuPDF AGPL/kereskedelmi feltételeit és a Qt terjesztési követelményeit Windows-csomag terjesztése előtt rendezni kell.
