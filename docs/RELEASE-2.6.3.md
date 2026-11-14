# EDPD Menedzser 2.6.3 – ellenőrzött Windows XP Luna Blue kiadás

Ellenőrzés: 2026-11-14T12:18:11+00:00.
A [Release](https://github.com/baloghim/beerkezett_posta_kezeles/releases/tag/v2.6.3) és a [Windows x64 ZIP](https://github.com/baloghim/beerkezett_posta_kezeles/releases/download/v2.6.3/EDPD-Manager-Windows-x64.zip) ténylegesen elérhető. A nyilvános ZIP-et visszatöltöttük: SHA-256 egyezik a mellékelt összeggel, minden ZIP-bejegyzés CRC-je hibátlan.

## A Luna megvalósítása

A Beállítások → Megjelenés → Felületi stílus új eleme **Windows XP Luna Blue**. Saját paletta és önálló Luna-QSS ág tartozik hozzá a meglévő `SurfaceThemeManager` alatt. Krémszínű, enyhén domború eszköztárak és fejlécek, telített királykék panelcímek, kék gombkeretek, meleg narancsos hover/fókusz, süllyesztett lenyomott állapot, szegmentált zöld folyamatjelző és világos, krémszínű párbeszédablakok jellemzik. A hárompaneles szerkezet, a 40/22 pixeles ikonok és a fő feliratok +2 pontos méretnövelése megmaradt.

A Longhorn üvegszerű kék eszköztára és hangsúlyos fénysávos panelcíme helyett más felületek és vezérlőállapotok készültek. A Longhorn Blue/Slate QSS-ének SHA-256 értéke bájtpontosan egyezik a 2.6.2-es kiadáséval. A Luna nem az operációs rendszer telepített XP-témáját használja. Nincs Microsoft msstyles/DLL/BMP, új betűkészlet, külső témamotor vagy új futásidejű függőség. A natív Windows ablakkeret/címsor megmaradt.

A Qt-független `edpd.surface_styles` névjegyzéket használja a korai profilátvétel, a központi kezelő, a stílusválasztó és a képek névképzése. A feloldás nem rögzített listavágásra épül. A gyorsítótár mindhárom alkalmazásstílust tárolja. Gyári stílusra váltáskor a QSS és a módosított paletta teljesen visszaáll, Longhornra váltáskor az eredeti Longhorn-megjelenés tér vissza.

A mentés azonnal érvényes, a Mégse nem módosítja a megjelenést; a választás a meglévő `%APPDATA%\EDPD\settings.json` fájlban marad meg. A váltás nem indít hálózati/ZIP-újraolvasást, nem cseréli le az ikontémát és nem módosítja a PDF eredeti tartalmát, lapját vagy rögzített nagyítását. A klasszikus XP-kék kijelölésen a szemantikus zöld/barna/piros szöveg legalább 4,5:1 kontrasztú világos megfelelővel jelenik meg, a modell eredeti színei és a nem kijelölt sorok változatlanok.

Mind a **12 ikontéma** működik az új felülettel, köztük SE98, Crystal SVG, Oxygen és Nuvola. A 2.6.2 ikonjai, szerepkiosztása, licencállományai és állandó EXE-emblémája változatlan. A fájlkezelést, a nyomtatást, az exportot, a tranzakciós visszaállítást, a zárolást és a példányvédelmet nem alakítottuk át.

## Tényleges képek

- [Luna/Longhorn összehasonlítás, öt valódi Qt-ablakképből](xp-luna-theme-comparison.png).
- [Használat és mind a hét egyedi alkalmazáskép](XP-LUNA.md): Luna + Crystal/SE98/Oxygen/Nuvola, Longhorn + Crystal összevetés, Luna Beállítások és valódi kicsomagolás.
- [A visszatöltött Windows EXE Luna + SE98 képe](windows-2.6.3-luna-se98.png).
- [A Windows EXE Luna Beállítások ablaka](windows-2.6.3-luna-settings.png).
- [A Windows EXE tényleges Luna-kicsomagolási ablaka](windows-2.6.3-luna-extraction.png).

A Linux képek futó Qt 5.15/Fusion alkalmazásból készültek, mesterséges helyi ZIP/PDF adatokkal. A Windows képek a Release csomagolt EXE-önellenőrzési képei közül származnak. Nincs generált látványterv vagy éles dokumentum. A teljes nyers képsorok a ZIP `modern-runner-selftest-screenshots/` és `surface-reports/` mappáiban is szerepelnek.

## Ellenőrzések

- Linux: **186 sikeres teszt, 1 Windows-specifikus kihagyás**. A hover/lenyomott/letiltott festési állapotokat közvetlen Qt-eseményekkel ellenőrizzük, OS-egérpozíciótól függetlenül.
- Windows Server 2022 runner: **188 sikeres teszt**, 0 hiba, 0 futási hiba, 0 kihagyás. [Meglévő Windows-workflow](https://github.com/baloghim/beerkezett_posta_kezeles/actions/runs/43593434766).
- **Nyolc tényleges csomagolt EXE-futtatás × 20 sikeres funkcionális ellenőrzés:** alap, Blue, Slate, Luna, Blue 125/150% és Luna 125/150%.
- Futtatásonként **144** Qt-stílus/felület/ikontéma kombináció és **12** főablak-viewport-próba; PDF eredeti bájtjai és színes pixelei, kiválasztott lap/nagyítás, állapotszínek, ikonméretek és paletta-visszaállítás megmaradtak.
- Minden futtatásban **9 Luna-párbeszédelrendezés**: Beállítások, Névjegy, folyamatablak mindhárom kért viewport mellett, belül maradó látható vezérlőkkel. A Luna indulási próbák külön a valódi kicsomagolási ablakot is rögzítik.
- **12 indulási tesztcsoport**: dupla indítás, inicializálás alatti második példány, külön mappák, lassú/elérhetetlen hálózat, hibás konfiguráció, normál és rendellenes bezárás utáni újraindítás; mind a 12 ikontéma és a hat Windows-felületi stílus tényleges új folyamatban visszatöltve.
- A letöltött ZIP **840 erőforrása és 54 licencállománya** bájtonként egyezik a forrással. A hétméretű fix EXE ICO és **109 natív bináris** auditja sikeres.

A natív fájlválasztók és az eredeti dokumentumkezelési folyamatok megmaradtak. A memory/object stresszteszt véges, nem minden környezetre kiterjedő szivárgás-bizonyíték.

## Méret és mérés

| Mérés | Érték |
| --- | ---: |
| 2.6.2 ZIP | 67,903,519 bájt |
| 2.6.3 ZIP | 73,503,817 bájt (70.10 MiB) |
| Változás | +5,600,298 bájt (+8.25%) |
| Mentett Luna, folyamat → splash | 389.088 ms |
| Mentett Luna, folyamat → főablak | 619.913 ms |
| Teljes témamátrix váltási mediánja | 34.284 ms |
| Teljes témamátrix váltási maximuma | 42.092 ms |

A ZIP a több skálázási/EXE-ellenőrzés nyers jelentéseit és képeit, valamint a Luna dokumentációs összehasonlítását is tartalmazza. Új grafikai futásidejű erőforráscsomag nem került be. Az időadatok egyetlen CI-futtatás adatai, nem ürített OS-gyorsítótárú hidegindítás és nem kontrollált benchmark. A teljes részfázisok a `startup-validation.json` fájlban vannak, személyes adat és PDF-tartalom nélkül.

## Kompatibilitás és Git

Változatlan alap: Python 3.10.11 x64, PySide2 5.15.2.1 / Qt 5.15.2, PyMuPDF 1.23.26 és a meglévő PyInstaller-spec. A Windows Server 2022 eredmény **nem Windows 10 1607 célgépes minősítés**. Az 1607-es rendszer, a valódi munkahelyi SMB/nyomtató és a fizikai Windows DPI-beállítás külön átvételi próba marad. A 125/150% ellenőrzés a Qt-folyamat skálázását állítja; a device pixel ratio a jelentésekben szerepel.

Forráscommit: `543845a5e60eacc43253ea8e28fdd33e611ea4a6`, annotált címke `v2.6.3`. A README közvetlen letöltési hivatkozása a ZIP tényleges ellenőrzése után frissül. A teljes forrás és jelentés hagyományos Git-feltöltéssel kerül a `main` ágra.

SHA-256: `8866be0e208ee61d0a9b4195888bf45c15fc77651235ea6a58d935fab289feaf`.
