# Ellenőrzési eredmények – 0.2.1

Dátum: 2026. november 12.

- Linux, Python 3.10.22: **31 sikeres teszt, 1 szabályosan kihagyott teszt**. A kihagyott teszt valódi Windows Qt DLL-eket vizsgál; a Windows workflow-ban végrehajtódik.
- Windows 2022 runner, Python 3.10.11 x64: az automatikus tesztcsomag sikeres, beleértve a nagy Qt exporttáblák és a szándékosan eltávolított CONCRT140.dll felismerésének ellenőrzését.
- [Javított teljes runtime build](https://github.com/baloghim/beerkezett_posta_kezeles/actions/runs/43225220899): **Success**.
- [v0.2.1 Windows build és GitHub Release](https://github.com/baloghim/beerkezett_posta_kezeles/actions/runs/43225724848): **Success**.
- [Release](https://github.com/baloghim/beerkezett_posta_kezeles/releases/tag/v0.2.1) · [Windows ZIP](https://github.com/baloghim/beerkezett_posta_kezeles/releases/download/v0.2.1/EDPD-Manager-Windows-x64.zip) · [SHA-256 fájl](https://github.com/baloghim/beerkezett_posta_kezeles/releases/download/v0.2.1/EDPD-Manager-Windows-x64.zip.sha256).

## A ténylegesen csomagolt EXE próbája

A kiadott ZIP `modern-runner-selftest.json` eredménye:

- Rendszer: Windows Server 2022, build **20348**, 64 bit, `frozen: true`.
- Python **3.10.11**, PySide2 **5.15.2.1**, Qt **5.15.2**, PyMuPDF **1.23.26**.
- `passed: true`, `windows1607_verified: false`.
- Nyolc sikeres funkcionális ellenőrzés: natív importok; hárompaneles GUI és napi ZIP-csoportosítás; ZIP-ből PDF-betekintés, lapozás és nagyítás; közös fájlzár; kicsomagolás és munkamappából megnyitás; két teljes oldal nyomtatási PDF-kimenete; napi törlés és ürítés; helyi beállítások és panelméretek megőrzése.

A beágyazott `native-dependencies.json` **107 natív PE-fájlt** vizsgál. Nincs hiba: x64 architektúra, ismert 1607 utáni közvetlen API-k hiánya, név szerinti belső importok, runtime-eredet és csomagolt alkalmazás/runtime DLL-ek megléte ellenőrizve. A dinamikus API-feloldásból következő OS-követelményeket ez nem bizonyítja.

## A közzétett ZIP letöltés utáni ellenőrzése

- Méret: **61,294,296 bájt**, 198 ZIP-bejegyzés.
- Teljes ZIP CRC-ellenőrzés: hibátlan.
- A közzétett SHA-256 fájl és a letöltött ZIP egyezik: `5f8fbdd600cc809e0f1eea7493f5822834f39bdd3fdf3079b387b8327924934d`.
- Windows EXE, Python310.dll, Qt5Widgets.dll, qwindows.dll, MuPDF DLL, MSVCP140.dll, **CONCRT140.dll**, VCRUNTIME140.dll és VCRUNTIME140_1.dll jelen van.
- Minden hivatkozott alkalmazás-, Qt-, Python-, MuPDF- és VC-runtime DLL megtalálható a csomagban. A Windows 10 beépített rendszer-DLL-jeit nem másoljuk a runnerből.
- Nincs Qt 6/PySide6 fájl a csomagban. A célgépes PowerShell-script UTF-8 BOM-ja megmaradt.

## Ami még a céges gépen szükséges

**Valódi Windows 10 1607 x64 (14393) gépet vagy VM-et a felhőkörnyezetből nem értünk el. A célgépes kompatibilitást ezért még nem állítjuk igazoltnak.** A felhasználó által elérhető céges gépen az [EXE-önellenőrzés](WINDOWS1607.md) futtatható, Python és fejlesztőeszközök telepítése nélkül. A külön 1607-es self-hosted CI-job nem futott.

A fizikai nyomtató és a több munkaállomásos SMB-megosztás próbája a [Windows-átvételi útmutató](WINDOWS-VALIDATION.md) szerint hátravan. Az automatikus tesztek nem használtak valódi NEAK adatot vagy megosztást.

## Korábbi kiadások

- **0.1.0:** Qt 6.8 alapú; a Qt dokumentált Windows minimuma 1809, így nem megfelelő a 1607-es célgéphez.
- **0.2.0:** a közzétett ZIP utóellenőrzésénél hiányzó CONCRT140.dll függőség derült ki. A modern runner rendszerbe telepített DLL-je ezt elfedte. A kiadás figyelmeztetéssel jelölt; helyette 0.2.1 használandó. A 0.2.1 buildben a teljes rögzített runtime-készletet explicit csomagoljuk, és a hiányzó ilyen DLL már kötelezően sikertelen auditot eredményez.
