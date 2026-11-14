# EDPD Menedzser 2.6.2 – SE98 és ellenőrzött Windows-kiadás

Ellenőrzés: 2026-11-14T11:37:29+00:00.
A [Release](https://github.com/baloghim/beerkezett_posta_kezeles/releases/tag/v2.6.2) és a [Windows x64 ZIP](https://github.com/baloghim/beerkezett_posta_kezeles/releases/download/v2.6.2/EDPD-Manager-Windows-x64.zip) ténylegesen elérhető. A nyilvános ZIP-et visszatöltöttük; SHA-256 egyezik a mellékelt összeggel, az összes ZIP-bejegyzés CRC-je hibátlan.

## Változás

Az **SE98** bekerült a Beállítások → Megjelenés → Ikontéma választóba. Így 12 téma választható; az alapérték továbbra is Crystal SVG. Az SE98 mentés után azonnal érvényes, újraindítás után visszatöltődik, és mindkét Longhorn-felülettel, valamint az összes rendelkezésre álló gyári Qt-stílussal működik.

A kiválasztott eredeti SE98-grafikák 19 szerepből **18-at** fednek le. A `width` szerep Crystal SVG-t használ; nem állítunk teljes saját lefedettséget. A munkamappa-ürítés eredeti SE98 mappa és ugyanazon téma törlésjelvényének 50%-os jobb alsó kombinációja, átszínezés nélkül. A többi 11 téma manifest-bejegyzése és eredeti/renderelt grafikai állományai összevetve változatlanok.

Forrás: [nestoris/Win98SE](https://github.com/nestoris/Win98SE), commit `a837b57a47242d6eefe63cadc9e6906a5be7e7a6`. A 18 szerep eredeti fájljai, a jelvény és SHA-256 értékeik a `src/edpd/assets/themes/se98/original/`, illetve a `themes.json` állományban vannak. A tároló GPL2 nyilatkozata, README-je, `someicons.md` eredetleírása és EDPD-módosításjelzése a `licenses/se98/` alatt, valamint a Windows ZIP-ben is megmarad.

Az SE98 a felhasználó kifejezett kérése alapján került be a korábban ismertetett fájljogi bizonytalanság mellett. A beépítés nem jelent új szerzői engedélyt, és az egyes Microsoft-eredetű fájlok jogait nem minősítjük igazoltnak. A [13 jelölt aktuális auditja](ICON-THEME-AUDIT-2.6.2.md) és a [gépi adatok](icon-theme-audit-2.6.2.json) ezt is rögzítik. A Buuf For Many Desktops továbbra sincs a csomagban.

A dokumentumkezelés, PDF-műveletek, visszaállítás, zárolás, helyi jelölések, példányvédelem és indulási folyamat változatlan. A meglévő PyInstaller-spec és Windows GitHub Actions-workflow készült el újra; nincs új csomagolórendszer vagy futásidejű függőség.

## Képi ellenőrzés

- [A hat főikon mind a 12 témával, 40 px](icon-toolbar-comparison.png).
- [A 19 szerep mind a 12 témával](icon-theme-comparison.png).
- [A tényleges csomagolt Windows EXE SE98 + Blue képe](windows-2.6.2-blue-se98.png).
- [Az SE98-at mutató kétválasztós Beállítások a Windows EXE-ben](windows-2.6.2-se98-settings.png).

A képeket tényleges fájlokból/Qt-ablakokból készítettük és szemrevételeztük, kizárólag szintetikus ZIP/PDF adatokkal. A PNG-k előre készülnek; futás közben nincs SVG-rasterizálás. Az SE98 önálló újragenerálása: `QT_QPA_PLATFORM=offscreen python scripts/generate_theme_assets.py --theme SE98`.

## Ellenőrzések

- Linux: **177 sikeres teszt, 1 Windows-specifikus kihagyás**; végleges forrásból 20 sikeres alkalmazás-önellenőrzés.
- Windows runner: **179 sikeres teszt**, 0 hiba, 0 futási hiba, 0 kihagyás. [Workflow](https://github.com/baloghim/beerkezett_posta_kezeles/actions/runs/43590357382).
- Öt tényleges csomagolt Windows EXE-futtatás × 20 sikeres funkcionális ellenőrzés: alap, Blue, Slate, Blue 125%, Blue 150%.
- Futtatásonként **108** Qt-stílus/felület/ikontéma kombináció és kilenc viewport-próba. Eredeti PDF-bájtok/pixelek, szemantikus színek és natív paletta-visszaállítás megmaradtak.
- **12 indulási tesztcsoport**: dupla indítás, inicializálás alatti második példány, külön mappák, lassú/elérhetetlen hálózat, hibás konfiguráció, normál és rendellenes leállás utáni újraindítás. Mind a 12 ikontéma – köztük SE98 – és az öt Windows-felületi stílus tényleges új folyamatban visszatöltve.
- A letöltött ZIP **840 erőforrása és 54 licencállománya** bájtonként egyezik a forrással. Az EXE fix ICO-ja hét méretben ellenőrzött.
- **109 natív bináris** statikus auditja sikeres.

## Méret és időmérés

| Mérés | Érték |
| --- | ---: |
| 2.6.1 ZIP | 67,410,488 bájt |
| 2.6.2 ZIP | 67,903,519 bájt (64.76 MiB) |
| Változás | +493,031 bájt (+0.73%) |
| Új profil, folyamat → splash | 603.226 ms |
| Új profil, folyamat → főablak | 810.472 ms |
| Stílus/felület/ikontéma váltás mediánja | 35.206 ms |
| Stílus/felület/ikontéma váltás maximuma | 44.742 ms |

Ezek CI-mérések, nem ürített operációsrendszer-gyorsítótárú hidegindítás vagy kontrollált teljesítmény-összehasonlítás. A részfázisok a ZIP `startup-validation.json` fájljában vannak. Nincs személyes adat vagy PDF-tartalom az időzítési naplóban.

A modern Windows Server 2022 runner nem helyettesíti a külön Windows 10 1607 célgépes, munkahelyi SMB- és nyomtatási átvételi próbát. A 125/150% ellenőrzés Qt-folyamatskálázás, nem a fizikai Windows asztal DPI-beállításának módosítása.

Forráscommit: `09dcb4aeb945df12408719eebbcec10f52644147`; annotált címke: `v2.6.2`. A README letöltési hivatkozása a ZIP tényleges ellenőrzése után frissül külön dokumentációs commitban.

SHA-256: `003c59637dc3d851bda5ca2705d2530fd67d1b4cda0089b4f2fc4ab308c3c4ce`.
