# Crystal ikonok – eredet és reprodukálhatóság

Forrás: https://github.com/dangvd/crystal-remix-icon-theme

Rögzített commit: `f8863b558b8eedf22caea0eabe18030bfcbe0783`.
Az upstream README szerint a készlet a KDE 3 Crystal Project és Crystal Clear
ikonjaiból készült (főként Crystal Project). Eredeti szerző: **Everaldo Coelho**;
modern átdolgozó: **Viet Dang (Đặng Việt Dũng)**. Az upstream **GNU LGPL** licencet
nevez meg, verzió nélkül. Az eredeti README változatlan másolatát és az LGPL 2.1,
LGPL 3.0 licencszöveget megőriztük a `licenses/crystal-remix/` alatt; ez nem egy
upstream által meg nem adott licencverzió választása.
A felhasznált állományok tényleges PNG-k, nem generált utánzatok és nem eredeti
SVG-források. A Crystal SVG arculati kéréshez a megjelölt valódi Crystal Remix
családot használtuk; nem nevezzük át a fájlokat SVG-vé.

## Tényleges forrásfájlok

Az eredetik: `src/edpd/assets/original/<méret>/<név>.png`.
A táblázat méretei az upstream `<méret>x<méret>/` könyvtárakra vonatkoznak;
csak ténylegesen létező képeket másoltunk. A 22, 32, 48, 64 és 128 pixeles
változatok közül az elérhetőket megőriztük. Nagyobb megjelenítéshez Qt-skálázás
használatos. A 2.3 fő eszköztára 40, a PDF-eszköztár 22 pixeles megjelenítést használ; a Qt az elérhető raszterekből méretez.

| Funkció / belső név | Upstream fájl a méretkönyvtáron belül | Meglévő méretek | Beépített célfájl |
| --- | --- | --- | --- |
| `extract` | `apps/ark.png` | 22, 32, 48, 64, 128 | `assets/icons/<méret>/extract.png` |
| `delete` | `places/user-trash-full.png` | 22, 32, 48, 64, 128 | `assets/icons/<méret>/delete.png` |
| `clear` | `places/folder.png` | 22, 32, 48, 64, 128 | `assets/icons/<méret>/clear.png` |
| `refresh` | `apps/system-software-update.png` | 22, 32, 48, 64, 128 | `assets/icons/<méret>/refresh.png` |
| `settings` | `actions/system-run.png` | 22, 32, 48, 64, 128 | `assets/icons/<méret>/settings.png` |
| `about` | `status/dialog-information.png` | 22, 32, 48, 64, 128 | `assets/icons/<méret>/about.png` |
| `first` | `actions/go-first.png` | 22, 32, 48, 64, 128 | `assets/icons/<méret>/first.png` |
| `previous` | `actions/go-previous.png` | 22, 32, 48, 64, 128 | `assets/icons/<méret>/previous.png` |
| `next` | `actions/go-next.png` | 22, 32, 48, 64, 128 | `assets/icons/<méret>/next.png` |
| `last` | `actions/go-last.png` | 22, 32, 48, 64, 128 | `assets/icons/<méret>/last.png` |
| `zoom_in` | `actions/zoom-in.png` | 22, 32 | `assets/icons/<méret>/zoom_in.png` |
| `zoom_out` | `actions/zoom-out.png` | 22, 32 | `assets/icons/<méret>/zoom_out.png` |
| `width` | `actions/zoom-fit-best.png` | 22, 32 | `assets/icons/<méret>/width.png` |
| `page` | `actions/zoom-fit-best.png` | 22, 32 | `assets/icons/<méret>/page.png` |
| `print` | `actions/document-print.png` | 22, 32 | `assets/icons/<méret>/print.png` |
| `zip` | `mimetypes/application-x-archive.png` | 22, 32, 48, 64, 128 | `assets/icons/<méret>/zip.png` |
| `pdf` | `mimetypes/application-pdf.png` | 22, 32, 48, 64, 128 | `assets/icons/<méret>/pdf.png` |
| `warning` | `status/dialog-warning.png` | 22, 32, 48, 64, 128 | `assets/icons/<méret>/warning.png` |
| `mail` | `actions/mail-message.png` | 22, 32 | `assets/icons/<méret>/mail.png` |

A 2.3 PDF mentési ikonja: `actions/document-save-as.png`, a tényleges upstream 22×22 és 32×32 változatokból. Az eredetik: `assets/original/22/save.png` és `assets/original/32/save.png`; beépített változatok: `assets/icons/<méret>/save.png`.

## Dokumentált EDPD-módosítások

- `extract`: az eredeti nyitott láda sárgás árnyalatot kap, a zöld nyíl megmarad.
- `delete`, `settings`: a valódi Crystal kuka és fogaskerék kék színezése az
  eredeti alfa, fényesség, árnyékolás és térbeli részletek megtartásával.
- `clear`: a Crystal mappa sárga színezése és a kék kuka ráhelyezése.
- `refresh`: a Crystal frissítési kör felső színes része kékre színezett;
  az alsó zöld rész és az eredeti grafikai részletek megmaradnak.
- `width`: Crystal nagyító + két Crystal oldalirányú nyíl; a `page` az eredeti
  teljes illesztési ikon. A két kép különböző.
- `app`: Crystal levélboríték + Crystal PDF-lap, rétegezve. PNG-méretekből
  16/24/32/48/64/128/256 pixeles, 32 bites ICO készült. A 256-os méret az
  elérhető eredeti raszterek skálázása, nem új vektoros rajz.
- Más ikonok az eredeti raszterekből származnak, szükség esetén méretezve.

Minden módosítás a `scripts/generate_icons.py` állományban van; nem kell az
upstream tárolót újra letölteni, mert az eredeti képek a projektben megmaradtak:

```bash
QT_QPA_PLATFORM=offscreen .venv-qt5/bin/python scripts/generate_icons.py
```

Ugyanez készíti a `docs/icon-comparison.png` képet a ténylegesen beépített
ikonfájlokból, funkciónevekkel. A generálás nem igényel új Python-függőséget.
Az `assets/manifest.json` rögzíti az upstream commitot, útvonalakat és méreteket.

## Csomagolás és ellenőrzés

A setuptools és a PyInstaller az eredeti és módosított képeket, az ICO-t és a
jegyzéket is csomagolja. A licencmappa külön szintén bekerül. Az alkalmazás és a
Névjegy ugyanazt az `app` grafikát használja; a Windows EXE az `edpd.ico` fájlt.
A Windows workflow `scripts/check_packaged_icons.py` ellenőrzése a valódi PE
`RT_GROUP_ICON` / `RT_ICON` erőforrásokat képkockánként összehasonlítja az ICO-val,
és a becsomagolt rasztereket a forrásfájlokkal. Nem csak a spec szövegét vizsgálja.
A csomagolt EXE önellenőrzése minden ikon tényleges Qt-betöltését is ellenőrzi.
A Windows tálca és Alt+Tab tényleges megjelenítése a célgépes átvétel része.
