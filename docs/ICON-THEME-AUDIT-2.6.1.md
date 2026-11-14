# EDPD Menedzser 2.6.1 – a 13 ikonjelölt ellenőrzése

Az ellenőrzés a megadott upstream tárolók tényleges fájljaira, README-, szerzői és licencállományaira épül. A „licenc ellenőrizve” a közzétett feltételek elolvasását jelenti; nem jogi minősítés és nem a teljes alkalmazás terjesztési engedélye. A források 2026. november 14-i, rögzített commitjai szerepelnek a manifestben.

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

## Beválogatás és kizárás

**11 valódi téma** választható. A Nuvola 18, az Oxylite 18, a Modern Office Day 15 saját szerepet ad. A többi beválogatott készlet 19-et. A felsorolt hat hiányzó szerep Crystal SVG-re esik vissza; a kiadott csomagban Qt standard fallbackre nincs szükség. A tartalék sorrend futás közben továbbra is Crystal → Qt standard. A Nuvola és a KDE Modern Classic korábbi szerepkiosztása változatlan.

**SE98:** a tároló GPL2 fájlja megvan, de a README „manual copy-paste fork” megjelöléssel Chicago95/Microsoft Memphis, Windows 98 SE/ME/2000 eredetet ismertet. Az egyes szükséges grafikákhoz önálló, igazolható Microsoft-engedély nem került elő. Emiatt egyetlen SE98-ikon sem kerül a programba. Ellenőrzött commit: `a837b57a47242d6eefe63cadc9e6906a5be7e7a6`.

**Buuf For Many Desktops:** a megadott Codeberg projekt HTTPS-kapcsolatát a menedzselt környezet proxyja 403-mal visszautasította. Így tartalma és licence nem ellenőrizhető; nem állítunk róla CC BY-NC vagy más feltételt. Nem helyettesítjük más, hasonló nevű Buuf-készlettel. Nem került be.

## Színes főikonok

A Papirus hat főszerepe a régi kis, többnyire fekete action-grafikák helyett saját 48 pixeles apps/places/status készletéből származik: archívum (`ark`), kuka, kék mappa, körbeforduló frissítésjel, színes beállításfogaskerék, kék információjel. A kuka saját piros törlésjelvényt kapott; a mappa ugyanezt használja. A We10X arany ZIP-et, saját lomtárat, sárga mappát saját törlésjelvénnyel, kék környilas frissítésikont, kék közepű fogaskereket és kék információjelet használ. Nincs átszínezés vagy más témából átvett főikon. A fájlonkénti útvonal és hash a manifestben van.

Az összes új készlet munkamappa-ürítése az adott téma eredeti mappájának és saját törlésjelének kombinációja: a jelvény az ikon jobb alsó, 50%-os méretű része. Az eredeti komponensek változatlan másolata és külön SHA-256 értéke is bekerül. A PDF-eszköztár kisebb, 22 pixeles action-ikonjai megmaradhatnak egyszerűbbnek.

## Új témák: eredet és licencek

- **Oxygen:** KDE Oxygen Team, a COPYING és REUSE.toml kifejezetten az ikonokra LGPL-3.0-or-later feltételt ad. A 2007-es eredeti művészek névsora az AUTHORS/COPYING állományokban szerepel. Saját színes 48×48-as KDE-grafikák, nem mesterséges rekonstrukciók. A PNG mellett a létező kapcsolódó szerkeszthető SVGZ-forrást is megőrizzük. A beállítás és kicsomagolás új kiválasztásához is ez az elv érvényes.

- **Win10Sur:** yeyushengfan258, COPYING: GPL-3.0. Az AUTHORS megnevezi az OSX_ONE alapot; ezt az eredeti kreditállományt is átadjuk. A megnevezett `unc926/OSX_ONE` GitHub-tároló az ellenőrzéskor „Repository not found” választ adott, ezért az alap külön történetét nem állítjuk függetlenül igazoltnak. A beépített konkrét fájlok a Win10Sur megadott commitjának GPL3 alatt közzétett állományai.

- **Oxylite:** a README általános GPL3 kijelentése mellett **minden kiválasztott, tényleges symlink-célhoz külön ellenőriztük a `licenses.yml` bejegyzését**. A kiválasztott elemek LGPL-3.0, illetve LGPL-3.0-or-later feltételűek, Oxygen és Adwaita alapokkal. A `license_details` megőrzi a fájlonkénti alapforrásokat és licenceket; a teljes upstream jegyzék, README és mindkét szükséges licencszöveg is mellékelt. A szélességigazításhoz nem találtunk megfelelő saját ikont; Crystal fallback. Az upstream PNG-változatot külön buildcélként állítja elő `rsvg-convert` használatával, nem tárol kész PNG-ket ebben a commitban. Mi a válogatott eredeti SVG-kből Inkscape-pel készítünk 22/40 PNG-t; az SVG-szűrők így nem a Qt 5 korlátozott SVG-kezelőjére maradnak.

- **WhiteSur:** Vince Liuice, GPL3 COPYING és AUTHORS. A normál `src/` családot választottuk, nem kevertük az alternative változattal. Az SVG2-hivatkozások és effektusok miatt előzetes Inkscape-rasterizálást kap; ezt a manifest jelöli.

- **Diagonal:** Tamás Csaba, a README/LICENSE szerint az **ikonok CC BY 4.0**, a telepítőszkriptek GPL3 alatt vannak. Csak a normál `base/` grafikai elemek kerülnek be; telepítők, disztribúciós és ablakkezelő-változatok nem. AUTHORS.md megőrzi az Evolvere, Mkos-Big-Sur, Qogir, WhiteSur, Papirus, Yaru és Kali ihletési/kompatibilitási krediteket. A CC BY licenc és az összetétel módosításjelzése mellékelt; a scripts licencét nem alkalmazzuk az ikonokra.

- **Modern Office Day:** DrMcC0y, a README GPL3 feltételt ír; az AUTHORS Breeze-forrást nevez meg, a README Mint Breeze Light/Breeze, Numix-Circle, Papirus és Hicolor alapokat is felsorol. Ezeket a krediteket változatlanul átadjuk, GPL3 és LGPL3 licencszöveggel. Nem állítjuk, hogy a teljes csomag minden ikonja új, önálló alkotás, vagy hogy a Hicolor önálló szerzői/licencjogosult. A konkrét átvett módosított fájlokat az upstream GPL3 közzététele alapján kezeljük. A négy hiányzó nagyítás/igazítás szerepet nem nevezzük saját lefedettségnek; Crystal helyettesíti. Az eredeti SVG2-hivatkozásokhoz itt is előzetes Inkscape-rasterizálás készül.

## Ellenőrizhető állományok

- `src/edpd/assets/themes.json`: témaazonosító, URL, commit, licenc/szerző, szerepenként tényleges upstream útvonal, kért alias, eredeti másolat, SHA-256, komponensek és átalakítás.
- `src/edpd/assets/themes/<id>/original/`: csak kiválasztott eredeti fájlok, forrásgrafikák és jelvények.
- `licenses/<id>/`: változatlan upstream licenc-/README-/szerzőállományok, szükséges teljes licencszövegek, EDPD-módosításjelzés.
- [19 szerep, mind a 11 téma](icon-theme-comparison.png); [hat főikon, mind a 11 téma, tényleges 40 px](icon-toolbar-comparison.png). A lapokon a szállított PNG-k vannak, nem látványtervek.
- [Géppel olvasható 13-jelöltes ellenőrzés](icon-theme-audit-2.6.1.json).

A képeket Qt 5-tel beolvastuk és szemrevételeztük. Papirus/We10X mind a hat főszerepe színes, a piros törlésjelvények elkülönülnek. A Nuvola/Modern Classic korábbi grafikái változatlanok. A forrás- és licencbájtokat a Windows build külön összeveti a csomaggal. Nincs új futásidejű könyvtár; az Inkscape csak a fejlesztői PNG-előállításhoz kell. Az alkalmazás saját kódjának és a már meglévő függőségeknek a licenckérdését ez nem változtatja meg.
