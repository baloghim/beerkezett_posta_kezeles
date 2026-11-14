# EDPD Menedzser 2.6.0 – ellenőrzött Longhorn Windows-kiadás

Ellenőrizve: 2026. november 14. A kiadást a nyilvános ZIP tényleges letöltése után, sikeres SHA-256- és teljes CRC-vizsgálattal minősítettük elkészültnek.

- Forráscommit: `fb391f5`, címke: `v2.6.0`.
- Meglévő Windows workflow: https://github.com/baloghim/beerkezett_posta_kezeles/actions/runs/43577752193
- Release: https://github.com/baloghim/beerkezett_posta_kezeles/releases/tag/v2.6.0
- Közvetlen ZIP: https://github.com/baloghim/beerkezett_posta_kezeles/releases/download/v2.6.0/EDPD-Manager-Windows-x64.zip
- ZIP: **66012665 bájt**; minden bejegyzés CRC-je hibátlan.
- SHA-256: `35a8d516b999ba37813651b4dfb92df92842ba6cd8d3640fdb50ba7077b081e6`; egyezik a közzétett `.sha256` fájllal.
- Windows JUnit: **157 sikeres, 0 hiba, 0 sikertelen, 0 kihagyott**.
- **Öt tényleges csomagolt EXE-futtatás**, összesen **100 sikeres funkcionális önellenőrzés**: Alapértelmezett, Blue, Slate, Blue 125% és Blue 150% Qt-skálázással. Minden futásban 20 ellenőrzés, nem csak a téma kirajzolása.
- **12 sikeres valódi folyamatindítási ellenőrzés**: korábbi példányvédelem és helyreállás mellett mindhárom mentett felületi téma külön EXE-folyamatban elindult.
- A csomagolt program **3 Qt-stílus × 3 felületi téma × 5 ikontéma** kombinációját vizsgálta mind az öt önellenőrzési futásban.
- Natív DLL-audit: **109 bináris**, üres hibalista.
- **433 grafikai/jegyzékerőforrás és 18 licencfájl** byte szerint egyezik a forrással. Az EXE mind a hét ICO-képkockája változatlan.
- A Blue és Slate QSS ellenőrzőösszege egyezik a forráséval; a Python-témamodulok a PyInstaller-csomagban ténylegesen működnek. Nincs külső letöltendő témaerőforrás.
- Helyi Linux-regresszió: **155 sikeres, 1 Windows-specifikus ellenőrzés kihagyva**; a későbbi, indulási időket megőrző kiegészítés célzott tesztjei is sikeresek.

## Megjelenés és visszaállítás

A Blue fényes kék-ezüst, a Slate visszafogottabb kékesszürke palettát használ ugyanazzal a QSS-sablonnal és komponensekkel. A Qt-stílus és az ikontéma külön választható. A felületi téma a meglévő `%APPDATA%\EDPD\settings.json` `surface_theme` mezőjében marad meg. Régi profilnál az alapérték Alapértelmezett. Mentés után azonnal vált, Mégse után nem változik.

A tesztek ellenőrizték az alkalmazás és több reprezentatív widget teljes natív palettájának visszaállítását, a dekoratív QSS teljes eltűnését, a PDF-cím elrejtését, a fontméretek megőrzését és az ismételt váltás utáni objektumszámot. A gyári Qt-stílus visszaáll, nem marad Longhorn-keret vagy háttér. A feldolgozott, részleges és hibás sorok zöld/barna/piros szövege kijelöléskor is ténylegesen kirajzolódik. A PDF eredeti bájtjai és rögzített nagyítású pixmapje minden kombinációban változatlan maradt.

A natív Windows címsor és ablakkezelő gombok megmaradtak. A meglévő menük, a három panel, az oszlopok, a fájlkezelési, nyomtatási és PDF-export szolgáltatások nem kaptak új üzleti működést. A felhasznált grafika saját Qt-színátmenet és egyszerű vezérlőrajzolás; nincs DWM/blur vagy animált háttér.

## Teljesítmény és méretezés

Az indulási jelentésből, folyamatindítástól számítva:

| Felületi téma | Indítókép | Főablak |
| --- | ---: | ---: |
| Alapértelmezett | 363.6 ms | 569.4 ms |
| Longhorn Blue | 368.4 ms | 588.5 ms |
| Longhorn Slate | 375.1 ms | 589.4 ms |

Ezek egymást követő új folyamatok egy modern Windows runneren, elkülönített profilban és helyi mesterséges adatokkal. Nem ürítettük az operációs rendszer fájlgyorsítótárát, ezért ez nem munkahelyi hidegindítási összehasonlítás. A témák között mért néhány tíz/száz ms eltérést az OS- és fontgyorsítótár is befolyásolja.

Az alapfutás 45 Qt-stílus/felület/ikon kombinációján a teljes váltás és eseményfeldolgozás mediánja **22.34 ms**, maximuma **27.42 ms** volt. A teszt nem csak a felületi témát, hanem a gyári Qt-stílust és az ikontémát is váltja; nem a kizárólagos felületitéma-váltás idejét állítjuk ebből. Rögzített PDF-nagyításnál a témaváltás nem kért új PDF-renderelést.

A 1280×720, 1600×900 és 1920×1080 méreteket mindhárom témával tényleges Qt-ablakmérettel vizsgáltuk. A Windows desktop fizikai felbontását nem állítottuk át; a teszt idejére a Qt-ablakokat a kért méretre rögzítettük. A 125/150%-os esetekben `QT_SCALE_FACTOR` és `PassThrough` biztosította a tört skálázást; a jelentésben a tényleges device pixel ratio is szerepel. Ez a Windows asztal DPI-beállításának célgépes váltását nem helyettesíti.

A Linux-stresszpróba 25 teljes témaciklus után figyelte a Python-memória növekedését és a Qt-widgetek számát; az EXE minden futásban további 15 ciklust végzett. Nincs ciklusonként hozzáadott widget vagy ismert progresszív megjelenítési eltérés. Véges automatizált stresszpróba alapján nem állítunk minden környezetre kiterjedő memóriaszivárgás-bizonyítékot.

## Tényleges képek és jelentések

A [Longhorn útmutató](LONGHORN.md) tartalmazza a hat kért, tényleges alkalmazásképet és az [összehasonlító képet](longhorn-theme-comparison.png). Ezek Linux Qt 5.15 Fusion képernyők, szintetikus dokumentumokkal; nem a referencia és nem generált látványtervek. A csomagolt Windows EXE-ből további natív képek készültek mindhárom felületről, Nuvolával, Beállításokról és a skálázási esetekről; a kiadási ZIP `modern-runner-selftest-screenshots/` és `surface-reports/` mappáiban vannak.

Gépi bizonyítékok a ZIP-ben: `test-results.xml`, `modern-runner-selftest.json`, `surface-validation.json`, `surface-reports/*.json`, `startup-validation.json`, `native-dependencies.json`, `icon-audit.json`.

## Kompatibilitás

A tényleges EXE Windows Server 2022 alatt futott, a rögzített Python 3.10.11 / Qt 5.15.2 / PySide2 5.15.2.1 / PyMuPDF 1.23.26 technológiai alapon. A modern runner sikere **nem** valódi Windows 10 1607 célgépes bizonyíték (`windows1607_verified=false`). A 20 pontos új önellenőrzés célgépes futtatása, a tényleges Windows DPI-beállítások, fizikai nyomtató és hivatali SMB-környezet átvétele külön szükséges. Minden automatikus írás/törlés elkülönített, mesterséges helyi adatokon futott.
