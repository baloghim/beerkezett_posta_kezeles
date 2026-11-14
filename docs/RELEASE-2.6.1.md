# EDPD Menedzser 2.6.1 – ellenőrzött Windows-kiadás

Ellenőrzés: 2026-11-14T11:12:40+00:00.
A [Release](https://github.com/baloghim/beerkezett_posta_kezeles/releases/tag/v2.6.1) és a [Windows x64 ZIP](https://github.com/baloghim/beerkezett_posta_kezeles/releases/download/v2.6.1/EDPD-Manager-Windows-x64.zip) ténylegesen elérhető. A nyilvános ZIP-et visszatöltöttük; SHA-256 egyezik a mellékelt összeggel, minden ZIP-bejegyzés CRC-je hibátlan.

## Eredmény

- Két Megjelenés-választó: Felületi stílus és Ikontéma. A telepített Fusion/Windows/Vista és Longhorn Blue/Slate egy listában vannak. Gyári stílusra váltás kikapcsolja a Longhorn QSS-t és palettát; Longhorn belső alapja Fusion.
- Automatikus profilátvétel: régi aktív Longhorn elsőbbséget kap, különben mentett gyári Qt-stílus; ismeretlen érték Fusion. Útvonalak, időzítők, ablakállapot és ikontéma megmaradnak. A konfiguráció továbbra is `%APPDATA%\EDPD\settings.json`.
- Mentés után azonnali váltás, Mégse nem ment. Megjelenésváltáskor nincs hálózati ellenőrzés, ZIP-újraolvasás vagy a rögzített nagyítású PDF újrarenderelése.
- 11 tényleges ikontéma; színes Papirus/We10X főikonok; új Oxygen, Win10Sur, Oxylite, WhiteSur, Diagonal és Modern Office Day. Nuvola/Modern Classic korábbi szerepkiosztása bájtonként összevetve változatlan.
- Minden új téma saját eredet-/licencállománnyal és rögzített commitokkal került be. A manifest szerepenként tartalmazza a forrásútvonalat, az eredeti másolatot, SHA-256 értéket, jelvénykomponenseket és renderelési módot.

## Mind a 13 jelölt

| Jelölt | Forrás elérhető? | Licenc ellenőrizve? | Saját lefedettség | Crystal fallback | Bekerült? |
| --- | --- | --- | --- | --- | --- |
| [Crystal SVG](https://github.com/dangvd/crystal-remix-icon-theme) | Igen | Igen | 19/19 | Nincs | Igen |
| [Nuvola](https://github.com/spartrekus/nuvola-icon-theme) | Igen | Igen | 18/19 | width | Igen |
| [KDE Modern Classic](https://github.com/nzoomed/kde-modern-classic) | Igen | Igen | 19/19 | Nincs | Igen |
| [Papirus](https://github.com/PapirusDevelopmentTeam/papirus-icon-theme) | Igen | Igen | 19/19 | Nincs | Igen |
| [We10X](https://github.com/yeyushengfan258/We10X-icon-theme) | Igen | Igen | 19/19 | Nincs | Igen |
| [Oxygen](https://github.com/KDE/oxygen-icons) | Igen | Igen | 19/19 | Nincs | Igen |
| [Win10Sur](https://github.com/yeyushengfan258/Win10Sur-icon-theme) | Igen | Igen | 19/19 | Nincs | Igen |
| [SE98](https://github.com/nestoris/Win98SE) | Igen | Igen; fájljogok tisztázatlanok | Nem minősített | – | Nem |
| [Oxylite](https://github.com/mx-2/oxylite-icon-theme) | Igen | Igen | 18/19 | width | Igen |
| [WhiteSur](https://github.com/vinceliuice/WhiteSur-icon-theme) | Igen | Igen | 19/19 | Nincs | Igen |
| [Buuf For Many Desktops](https://codeberg.org/eudaimon/buuf-for-many-desktops.git) | Nem, proxy 403 | Nem | Nem minősített | – | Nem |
| [Diagonal](https://github.com/tamascsabi/Diagonal-icon-theme) | Igen | Igen | 19/19 | Nincs | Igen |
| [Modern Office Day](https://github.com/DrMcC0y/Modern-Office-Day-Icons) | Igen | Igen | 15/19 | page, width, zoom_in, zoom_out | Igen |


Részletes licenc-/forrásbizonyíték, kizárási indokok és Papirus/We10X-változtatások: [13-jelöltes audit](ICON-THEME-AUDIT-2.6.1.md). Gépi adatok: [JSON](icon-theme-audit-2.6.1.json). A SE98 fájljogai nem tisztázottak; a Buuf megadott forrását a környezeti proxy blokkolja, ezért egyik sem szerepel a csomagban. Win10Sur AUTHORS megőrzött OSX_ONE-alapjának régi GitHub-linkje már nem elérhető; ezt az audit külön jelzi.

A fallbackek száma hat: Nuvola `width`; Oxylite `width`; Modern Office Day `zoom_in`, `zoom_out`, `width`, `page`. Mind Crystal SVG, Qt standard fallback a kiadott erőforráskészletben nincs. Nem állítunk saját teljes lefedettséget ezekre a témákra.

## Képek és források

- [19 szerep × 11 téma](icon-theme-comparison.png).
- [Hat főikon × 11 téma, tényleges 40 px](icon-toolbar-comparison.png).
- [Az új, kétválasztós Beállítások – Linux Qt](longhorn-blue-settings.png).
- [A tényleges csomagolt Windows EXE Blue/Crystal képe](windows-2.6.1-blue-crystal.png), a visszatöltött Release önellenőrzési képei közül.
- A képek tényleges szállított PNG-ket mutatnak, nem generált látványtervek. A PDF-eszköztár 22, a főikonok 40 pixelesek. Futás közben nincs SVG-rasterizálás; az Oxylite, WhiteSur és Modern Office SVG2/effektusaihoz Inkscape 1.4 készítette az előzetes PNG-ket. Nincs új futásidejű függőség.

## Ellenőrzések

- Linux: **175 sikeres teszt, 1 Windows-specifikus kihagyás**; az utolsó választósorrend-változás után 50 célzott UI/ikon teszt újrafuttatva. A végleges forrás alkalmazás-önellenőrzése mind a 20 pontban sikeres.
- Windows Server 2022 runner: **177 teszt**, 0 hiba, 0 futási hiba, 0 kihagyás. [Meglévő workflow](https://github.com/baloghim/beerkezett_posta_kezeles/actions/runs/43588441090).
- Öt tényleges csomagolt Windows EXE-futtatás × 20 sikeres funkcionális ellenőrzés: alap, Blue, Slate, Blue 125%, Blue 150%. Mindegyik a valódi kétválasztós ablakot és mind az öt Windows-felületi stílust is ellenőrzi.
- Futtatásonként **99** natív Qt-stílus/felület/ikontéma kombináció, kilenc tényleges viewport-próba; PDF eredeti bájtjai/pixelei, szemantikus táblázatszínek és paletta-visszaállítás megmaradtak.
- 12 indulási ellenőrzési csoport: második példány, gyors dupla indítás, külön mappák, inicializálás alatti indítás, késleltetett és elérhetetlen hálózat, hibás konfiguráció, normál/crash utáni újraindítás; mind a 11 ikontéma és az öt egységes felületi stílus új folyamatban visszatöltve.
- 109 natív bináris statikus auditja sikeres. Fix EXE ICO: 16/24/32/48/64/128/256 px. **785 erőforrás és 50 licencállomány** a letöltött ZIP-ben bájtonként megegyezik a forrással.
- Változatlan technológia: Python 3.10.11 x64, PySide2 5.15.2.1 / Qt 5.15.2, PyMuPDF 1.23.26, meglévő PyInstaller-spec és Windows Actions-folyamat.

## Méret és indulási mérések

2.6.0 ZIP: **66,012,665 bájt**. 2.6.1 ZIP: **67,410,488 bájt (64.29 MiB)**. Növekedés: **+1,397,823 bájt (+2.12%)**. Csak kiválasztott grafikai fájlok, komponensek, források és szükséges licencanyagok kerülnek be; teljes Linux-tématelepítők nem.

| Mérés | 2.6.0 | 2.6.1 |
| --- | ---: | ---: |
| Új profil, folyamat → splash | 395.386 ms | 301.900 ms |
| Új profil, folyamat → főablak | 606.467 ms | 483.188 ms |
| Mentett Fusion, folyamat → főablak | – | 522.274 ms |
| Mentett Windows, folyamat → főablak | – | 452.099 ms |
| Mentett windowsvista, folyamat → főablak | – | 461.778 ms |
| Mentett Longhorn Blue, folyamat → főablak | – | 478.970 ms |
| Mentett Longhorn Slate, folyamat → főablak | – | 451.616 ms |

A teljes stílus/felület/ikontéma-váltási mátrix mediánja **26.358 ms**, maximuma **35.544 ms**. Ezek egy-egy CI-futtatás mérései, nem kontrollált teljesítményverseny és nem ürített operációsrendszer-gyorsítótárú hidegindítás. A részfázisok a ZIP `startup-validation.json` fájljában vannak; személyes útvonal/PDF-tartalom nincs az időzítési naplóban.

## Korlátok és Git

A Windows Server 2022 eredmény nem Windows 10 1607 célgépes minősítés. Az 1607-es rendszer, a valódi munkahelyi SMB-megosztás, nyomtató és fizikai DPI-beállítás külön átvételi próba marad. A 125/150% teszt a Qt folyamat skálázását állítja. Az EDPD saját kódjának korábban rögzített licencelési helyzetét ez a kiadás nem változtatja meg.

Forráscommit: `e8e0bfa26daeaa5df21f5ff1259c8fcff1e3e948`; annotált kiadási címke: `v2.6.1`. Hagyományos `git push` sikeres. A README ellenőrzött letöltési linkje külön dokumentációs commitban frissül a ZIP tényleges ellenőrzése után.

SHA-256: `bf5698fe9fa801000041c3956f7c2061b78968a4e0e2ac75b8872bb3b715ca30`.
