# EDPD Menedzser – ikontémák

A Beállítások → Megjelenés → Ikontéma választó első öt, megőrzött témája: **Crystal SVG**, **Nuvola**, **KDE Modern Classic**, **Papirus**, **We10X**. Az alapérték Crystal SVG. A Felületi stílus és az Ikontéma két külön választó; összesen 11 ikontéma van. Hat új készlet és a 13 jelölt teljes vizsgálata: [2.6.1 audit](ICON-THEME-AUDIT-2.6.1.md). A mentett `icon_theme` mező a változatlan `%APPDATA%\EDPD\settings.json` fájlban található. Mentés után az ikonok újraindítás nélkül frissülnek; egy pusztán megjelenést érintő változtatás nem indít hálózati ellenőrzést vagy ZIP-újraolvasást.

A központi `edpd.ui.icons.IconThemeManager` logikai szerepeket old fel és gyorsítótárazza a QIcon objektumokat. A fő és PDF-eszköztár, a napi és munkamappa-lista, a helyi menük és a kicsomagolási/betekintési párbeszéd ikonfrissítési jelre váltanak. A Névjegy **gombja** témát vált; az alkalmazás saját emblémája és az EXE hétméretű ICO-erőforrása állandó.

Hiányzó szerepnél először az azonos Crystal SVG funkció, azután Qt standard ikon jelenik meg. Ismeretlen vagy nem telepített téma esetén Crystal SVG lép életbe. A Nuvola szélességigazító szerepe dokumentált Crystal fallback; a többi 18 szerep saját Nuvola-fájl. Az Oxygen, Win10Sur, WhiteSur és Diagonal 19 saját szerepet ad; Oxylite 18-at (width fallback), Modern Office Day 15-öt (zoom_in, zoom_out, width, page fallback). Papirus és We10X 19 szerepe megmarad, a hat főikon színes lett.

## Eredet és licencek

| Választó neve | Tényleges forrás és szerző | Licenc és megőrzött bizonyíték |
| --- | --- | --- |
| Crystal SVG | [Crystal Remix](https://github.com/dangvd/crystal-remix-icon-theme), Everaldo Coelho, Viet Dang (Đặng Việt Dũng), `f8863b558b8eedf22caea0eabe18030bfcbe0783` | Az upstream GNU LGPL-t ír, verzió nélkül. Nem állítunk konkrét verziót. `licenses/crystal-remix/`, `assets/manifest.json`; a korábbi EDPD változatok színezett/kombinált elemei változatlanok. |
| Nuvola | David Vignoni; a [spartrekus tükör](https://github.com/spartrekus/nuvola-icon-theme) `fb94aa21035d19c2ec68d69ec0ab21697a73e7c2` commitjának **nuvola-icon.tar.gz** eredeti, 32×32 PNG-fájljai | **LGPL-2.1-or-later**, a beágyazott Debian copyright `Files: IconThemes/nuvola/*` bejegyzése alapján; `licenses/nuvola/DEBIAN-copyright` és `LGPL-2.1.txt`. A tükör gyökérkönyvtárának általános GPL3 fájlja helyett az eredeti archívum konkrét Nuvola-bejegyzését dokumentáljuk. |
| KDE Modern Classic | [nzoomed/kde-modern-classic](https://github.com/nzoomed/kde-modern-classic), Shaun Belcher és a történeti KDE Classic művészei, `466f093bf391f80c67cef60a24d4013be2536707` | **LGPL-3.0-or-later**; `licenses/modern-classic/` tartalmazza a COPYING, COPYING.LESSER, AUTHORS, mindkét README és a történeti elemek megengedő LICENSE-KDE-Classic szövegét. |
| Papirus | [Papirus Development Team](https://github.com/PapirusDevelopmentTeam/papirus-icon-theme), Alexey Varfolomeev, Andrew Chadwick és közreműködők; a pontos commit a manifestben | **GPL-3.0**; `licenses/papirus/LICENSE`, AUTHORS és README. |
| We10X | [yeyushengfan258/We10X-icon-theme](https://github.com/yeyushengfan258/We10X-icon-theme), yeyushengfan258; az AUTHORS az Ubuntu Yaru alapot is megnevezi, `0f52ff2dce554146f8f76ab2c7a5968fd773400d` | **GPL-3.0**; `licenses/we10x/COPYING`, AUTHORS és README. |

**KDE Modern Classic eredetére vonatkozó pontosítás:** maga az upstream minden ikonját Claude segítségével, a szerző irányítása alatt készített SVG-rekonstrukcióként ismerteti. Az EDPD ezek ténylegesen közzétett upstream fájljait használja; nem rajzol vagy generál saját helyettesítő grafikát. A témát nem nevezzük a történeti KDE Classic eredeti SVG-készletének vagy kizárólag kézzel rajzolt készletnek. Az upstream erre vonatkozó teljes tájékoztatását és licencét a csomag is megőrzi.

A `src/edpd/assets/themes.json` szerepenként megadja az eredeti upstream fájlnevet, a beépített eredeti másolatot és SHA-256 értékét, továbbá a forrás URL-jét, commitját és licencét. Nuvolánál a teljes eredeti archívum SHA-256 értéke is szerepel. A témák válogatott részei kerülnek a csomagba, nem a teljes asztali ikonkészletek.

## Újra előállítható erőforrások és összehasonlítás

A változatlan eredeti SVG/PNG-k az `assets/themes/<azonosító>/original/` mappákban vannak. A `scripts/generate_theme_assets.py` Qt 5.15 SVG-rendereléssel/méretezéssel, a manifestben jelölt SVG2/effektusos fájloknál buildidejű Inkscape használatával 22 és 40 pixeles PNG-t készít belőlük; ez képfájlformátum-konverzió, nem új ikonok rajzolása. Futás közben az EDPD a PNG-ket tölti, SVG-rasterizálásra nincs szükség. A források, az átalakító és a licencek a Git-repóban vannak; az eredeti fájlok és licencek a Windows ZIP-be is bekerülnek.

```bash
QT_QPA_PLATFORM=offscreen python scripts/generate_theme_assets.py
```

Az [összehasonlító kép](icon-theme-comparison.png) ugyanazt a 19 szerepet mutatja 11 oszlopban, a ténylegesen beépített ikonokkal. A fallbacket felirat jelzi. A csomagellenőrzés minden erőforrás fájlbájtjait és az EXE hét ICO-képkockáját összeveti a forrással. A csomagolt önellenőrzés mind a 11 témát tényleges Qt-felületen kapcsolja át.

A PDF-eszköztárban hat helyen további 6 pixeles térköz van; a 2.5-től a Szélesség és Teljes oldal között is. A Nyomtatás és PDF mentése natív gombkeretet használ, az ikon és felirat között kifejezett 8 pixeles hézaggal. A meglévő QActionok, engedélyezési állapotok és PDF-műveletek változatlanok.

[A fő eszköztár hat ikonja mind a 11 témával](icon-toolbar-comparison.png).
