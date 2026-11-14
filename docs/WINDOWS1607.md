# EDPD Menedzser – Windows 10 1607 x64 (build 14393)

A célplatform adott: a céges Windows frissítése nem előfeltétel. Az alkalmazás továbbra is teljes Manager, a hárompaneles felület és valamennyi munkafolyamat megmarad.

## Miért váltunk Qt 5-re?

A korábbi PySide6 6.8.3 / Qt 6.8 dokumentált Windows minimuma **Windows 10 1809**. A 1607-es build ezen kívül esik. A teljes eredeti loader-hiba és célgépes vizsgálat nélkül nem állítjuk, hogy kizárólag ez okozta a DLL-hibát, de ez önmagában indokolja a csomag cseréjét.

Elsőként a kért PySide2-átállást vizsgáltuk. Az 5.15.2.1 PyPI-csomag saját Qt **5.15.2** könyvtárakat tartalmaz, és Python 3.10-hez létezik Windows x64 wheel. A Qt 5.15.2 dokumentáció Windows 7/8.1/10 támogatást sorol fel. Így a meglévő Qt Widgets felület megőrizhető, nem szükséges Tkinterre átírni. Qt WebEngine, böngésző és külső PDF-néző nincs a megoldásban.

| Összetevő | Rögzített Windows buildverzió | Vizsgálat |
| --- | --- | --- |
| CPython x64 | 3.10.11 | Hivatalos Windows installer, dokumentált Windows 8.1+ alap. Beágyazva a kiadásba. |
| PySide2 / shiboken2 | 5.15.2.1 | Qt 5.15.2, korábbi Windowsokat támogató kiadás; saját app-local VC DLL-ek. |
| PyMuPDF | 1.23.26 | CPython 3.10 Windows x64 wheel; `fitz` import. |
| PyMuPDFb / MuPDF DLL | 1.23.22 | A PyMuPDF 1.23.26 által előírt bináris társfüggőség; csomagolva. |
| PyInstaller | 6.12.0 | Dokumentált Windows 8+ alap; előre fordított bootloader. |
| PyInstaller hooks | 2025.1 | Rögzített csomagolóhookok. |
| VC-runtime | Python 3.10.11 és PySide2 wheel saját DLL-jei | A Python vcruntime DLL-jei a rögzített interpreterből, a C++ runtime DLL-ek a Qt wheelből származnak; ezt hash-ellenőrzés kényszeríti ki. |
| UCRT | Windows 10 beépített változata | Nem másoljuk a modern runner UCRT-jét a csomagba. |

A spec a teljes rögzített VC DLL-készletet is hozzáadja: a DLL-csere után például a régebbi MSVCP140 `CONCRT140.dll` függőségét is biztosítani kell. A statikus ellenőrzés a hiányzó alkalmazás- és runtime-DLL-eket is hibának tekinti, akkor is, ha a modern runner rendszerpéldánya elérhető.

A natív függőségek régebbi verzióinak használata tudatos kompatibilitási kompromisszum. Nem jelent mai upstream karbantartási támogatást. Az újabb natív verziókra frissítés csak újabb célgépes próbával végezhető.

A PDF-képekhez saját tulajdonú Qt-képpuffert készítünk a beépített PPM-dekóderen keresztül. A PySide2 alatt problémás, Python bytes-puffert kölcsönző QImage-konstruktort eltávolítottuk a betekintőből és a nyomtatásból.

## Melyik ellenőrzés mit bizonyít?

1. A pytest a munkafolyamatokat vizsgálja, ideiglenes adatokkal.
2. A **csomagolt EXE** modern Windows runneren saját GUI-val, Qt Windows platformpluginnal, PDF-rendereléssel, nyomtatási PDF-kimenettel és fájlműveletekkel önellenőrzést futtat. Nem csak a Python-forrás indulását ellenőrizzük.
3. A statikus PE-vizsgálat leltározza a csomag minden EXE/DLL/PYD fájlját, azok importjait és hash-ét. Ellenőrzi az x64 architektúrát, a csomagolt DLL-ek közötti név szerinti importok feloldhatóságát, a VC-runtime eredetét, a Qt 6 hiányát és ismert 1607 utáni közvetlen API-importok hiányát. A dinamikus API-feloldás és minden OS API viselkedése ebből nem bizonyítható.
4. **Csak a tényleges Windows 10 1607 x64 rendszeren sikeresen végzett EXE-próba igazolja ezen a rendszeren az indítást.** Az eredményben a modern runneren `windows1607_verified: false` marad. Windows Server 2016 azonos buildszáma sem kerül Windows 10 munkaállomásként elfogadásra.

A fejlesztői felhőgép Linux, külön Windows 1607-es VM-et nem használtunk. A felhasználó a céges célgépen a korábbi **0.2.1** csomagolt EXE önellenőrzését lefuttatta, és az `EDPD-1607.json` eredményt megküldte: **Windows 10 x64, build 14393, munkaállomás; mind a nyolc ellenőrzés sikeres, `windows1607_verified: true`, `error: null`.** Ez a 0.2.1 kiadás indítását és az akkori funkciókat igazolja a vizsgált céges gépen. **A 2.6 ugyanazokat a rögzített natív verziókat használja; az új alkalmazás húsz ellenőrzéses célgépes próbája még szükséges.** A fizikai nyomtató és a többgépes SMB-működés külön átvételi próbát igényel. [Részletes eredmények](VALIDATION.md).

## Ellenőrzés a céges gépen – telepítés nélkül

1. Az új ZIP teljes tartalmát bontsa ki **új helyi mappába**. Ne másolja rá a régi Qt 6-os verzióra, és ne csak az EXE-t másolja át.
2. A kibontott `EDPD-Manager` mappában nyisson Parancssort, és futtassa:

```bat
EDPD-Manager.exe --self-test --require-windows1607 --report "%USERPROFILE%\Desktop\EDPD-2.6.0-1607-result.json"
```

3. A teszt röviden megnyitja a felületet, kizárólag a felhasználó ideiglenes mappájában készít szintetikus dokumentumokat, majd bezár. Nem olvassa a valódi H:/G: mappát, nem írja felül a felhasználói beállításokat, és nem nyomtat fizikai nyomtatóra.
4. A JSON-fájl `application_version` mezőjében 2.6.0 szerepeljen, és a húsz ellenőrzés között a megszakítás/visszaállítás, az eredeti PDF mentése, a helyi feldolgozási jelölés és az öt ikontéma betöltése, az EDPD Menedzser név, a fő eszköztár betűmérete, a PDF-lapozás görgetés-visszaállítása és az egységes PDF-eszköztár-térköz is legyen sikeres. A `passed`, `windows1607_verified` és `host.frozen` értékeknek egyaránt `true` értéket kell mutatniuk. Az OS-buildnek 14393-nak kell lennie. Sikertelenségnél az `error` mező, illetve a teljes Windows DLL-hibaüzenet segít a javításban.

Opcionálisan a mellékelt PowerShell-script is futtatható, ha a vállalati szabályzat engedi:

```powershell
.\Test-Windows1607.ps1
```

A script UTF-8 BOM kódolással készül, így a Windows PowerShell 5.1 is helyesen olvassa a magyar szöveget. Ellenőrzi az OS-t, az EXE kilépési kódját, a friss JSON-eredményt és az időtúllépést is. Nem igényel rendszergazdát, nem telepít semmit, és nem módosítja a PowerShell végrehajtási házirendjét. Ha a vállalati policy tiltja a scripteket, a fenti közvetlen EXE-parancs használható.

Az önellenőrzés sikere után a fizikai nyomtató és a kétgépes SMB-megosztás próbája a [külön útmutató](WINDOWS-VALIDATION.md) szerint szükséges.

## Opcionális automatikus valódi 1607 teszt

A GitHub Actions `workflow_dispatch` bemenetén a `validate_windows1607` kapcsoló külön, `self-hosted, Windows, X64, win10-1607` címkékkel ellátott tesztgépen is ellenőrizheti a kész ZIP-et. Alapból ki van kapcsolva, nincs ilyen gép feltételezve, PR-ból nem fut. Csak erre kijelölt tesztgépre telepíthető runner; a céges munkaállomáson ehhez nincs szükség új szoftverre, ott a mellékelt EXE-önellenőrzés használható. A régi gépen futó opcionális job natív Windows PowerShell-lel tölti le és ellenőrzi az aktuális artifactot, nem igényel új Node.js-alapú actiont. A GitHub runner szolgáltatásnak külön támogatnia kell a régi vendég OS-t; ennek hiányában a közvetlen offline EXE-próba használható.

## Hivatalos források

A vizsgálat során a Qt oldal közvetlen elérését a hálózati házirend tiltotta; az alábbi hivatalos GitHub-forrásokat olvastuk:

- [Qt 6.8 támogatott platformok](https://github.com/qt/qtdoc/blob/v6.8.3/doc/src/platforms/supported-platforms.qdocinc)
- [Qt 5.15.2 támogatott platformok](https://github.com/qt/qtdoc/blob/v5.15.2/doc/src/platforms/supported-platforms.qdocinc)
- [PySide2 5.15.2.1 PyPI](https://pypi.org/project/PySide2/5.15.2.1/)
- [CPython 3.10.11 Windows-támogatás](https://github.com/python/cpython/blob/v3.10.11/Doc/using/windows.rst)
- [PyMuPDF 1.23.26 telepítés és Windows DLL-függőségek](https://github.com/pymupdf/PyMuPDF/blob/1.23.26/docs/installation.rst)
- [PyInstaller 6.12.0 rendszerkövetelmények](https://github.com/pyinstaller/pyinstaller/blob/v6.12.0/doc/requirements.rst)
