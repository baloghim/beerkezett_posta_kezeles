# Feldolgozottsági ikonok – EDPD Menedzser 2.6.4

A két ikonszerep a `themes.json` fájlban témánként a `status_icons` alatt szerepel.
Témánként az `original/` könyvtár tartalmazza az ikonforrásokat, a `22/` és `40/` könyvtár pedig a `processed.png` és `unprocessed.png` változatokat. A saját rajzokra a repó `LICENSE` fájlja vonatkozik.
A licencszövegek a repó `licenses/` könyvtárában, a forráskivonatok és az átalakítások a manifestben találhatók.
Az egyszínű forrásokhoz a maszk alakját megtartottuk és világos kontúrt adtunk a sötét háttérhez.

| Téma | Zöld pipa forrása | Semleges jelölés forrása | Licenc |
| --- | --- | --- | --- |
| Crystal SVG | `22x22/actions/dialog-ok.png` | `unprocessed.svg` (EDPD, projektlicenc) | GNU LGPL (upstream version unspecified) |
| Nuvola | `nuvola-icon.tar.gz!usr/share/icons/nuvola/22x22/actions/dialog-ok.png` | `unprocessed.svg` (EDPD, projektlicenc) | LGPL-2.1-or-later (Nuvola-specific Debian copyright entry) |
| KDE Modern Classic | `KDE-Modern-Classic/scalable/actions/dialog-ok.svg` | `unprocessed.svg` (EDPD, projektlicenc) | LGPL-3.0-or-later |
| Papirus | `Papirus/22x22/actions/object-select.svg` (színezve) | `Papirus/22x22/symbolic/status/checkbox-symbolic.svg` (színezve) | GPL-3.0 |
| We10X | `src/actions/22/dialog-ok-apply.svg` (színezve) | `src/status/symbolic/checkbox-symbolic.svg` (színezve) | GPL-3.0 (upstream COPYING; Yaru attribution in AUTHORS) |
| Oxygen | `22x22/actions/dialog-ok-apply.png` | `unprocessed.svg` (EDPD, projektlicenc) | LGPL-3.0-or-later |
| Win10Sur | `src/actions/16/dialog-ok-apply.svg` (színezve) | `src/status/symbolic/checkbox-symbolic.svg` (színezve) | GPL-3.0 |
| Oxylite | `actions/dialog-apply.svg` | `unprocessed.svg` (EDPD, projektlicenc) | LGPL-3.0-or-later |
| WhiteSur | `src/actions/24/dialog-ok-apply.svg` (színezve) | `src/status/symbolic/checkbox-symbolic.svg` (színezve) | GPL-3.0 |
| Diagonal | `base/actions/16/dialog-ok-apply.svg` (színezve) | `base/actions/16/checkbox.svg` (színezve) | CC-BY-4.0 (icons; upstream declaration); retained per-file notices |
| Modern Office Day | `actions/16/dialog-ok-apply.svg` (színezve) | `unprocessed.svg` (EDPD, projektlicenc) | GPL-3.0 (theme); retained upstream notices |
| SE98 | `SE98/actions/22/dialog-ok.png` (színezve) | `unprocessed.svg` (EDPD, projektlicenc) | GPL-2.0 (upstream repository declaration); individual Microsoft-derived artwork rights not independently established |

A Menedzser képe Linuxon, a tényleges Qt-ablakról készült, mesterséges ZIP- és PDF-adatokkal. Az ikon-összehasonlítás a futáskor betöltött 22 pixeles ikonokat mutatja világos és sötét háttéren.
