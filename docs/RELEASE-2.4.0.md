# EDPD 2.4.0 – ellenőrzött Windows-kiadás

Ellenőrizve: 2026. november 13. A kiadást csak a ténylegesen letöltött ZIP vizsgálata után minősítettük elkészültnek.

- Forráscommit: `ddb8efa`, kiadási címke: `v2.4.0`.
- Meglévő Windows workflow: https://github.com/baloghim/beerkezett_posta_kezeles/actions/runs/43428256223
- Release: https://github.com/baloghim/beerkezett_posta_kezeles/releases/tag/v2.4.0
- Ténylegesen letöltött ZIP: https://github.com/baloghim/beerkezett_posta_kezeles/releases/download/v2.4.0/EDPD-Manager-Windows-x64.zip
- ZIP: **63733581 bájt**, minden bejegyzés CRC-ellenőrzése sikeres.
- SHA-256: `9e3971eab76bcb0a2240a25ee53e1a020ef3db9b3a001c9cb70648a94d3b76f8`; egyezik a közzétett `.sha256` fájllal.
- JUnit: **138 teszt, 0 sikertelen, 0 hiba, 0 kihagyott**.
- Csomagolt EXE: **2.4.0**, `host.frozen=true`, **14 sikeres funkcionális önellenőrzés**.
- Az új EXE-t további **11 valódi folyamatindítási ellenőrzés** vizsgálta; `frozen_executable=true`, `platform=win32`.
- Tényleges alsó oszlopok: **Dátum, Fájlnév, Méret**; arányok 21/64/15%, változatlan forrásnapképzés és rendezés.
- Mind az öt mentett téma valós új EXE-folyamatban is elindult: Crystal SVG, Nuvola, KDE Modern Classic, Papirus, We10X.
- Natív DLL-audit: **109 bináris**, üres hibalista.
- EXE ICO: **16/24/32/48/64/128/256** pixeles képkockák; mind a korábbi változatlan ICO-val egyezik.
- **433 erőforrás és 18 licencfájl** byte szerint egyezik a forrással, beleértve az eredeti SVG/PNG-ket és a manifestet is.
- A főablak/PDF-eszköztár/lista/helyi menü témaváltása, a fallback és a nagyobb térközök tesztelve vannak. Külön képi regresszióteszt védi a Nyomtatás/PDF mentése gombok tényleges ikonrajzolását.

## A becsomagolt Windows EXE indulási mérése

A runner Windows Server 2022 (build 20348), Python 3.10.11 x64, Qt 5.15.2 / PySide2 5.15.2.1. A próba új felhasználói profilt és mesterséges helyi mappákat használt; a teljes OS-fájlgyorsítótárat nem ürítette.

| Folyamatindítástól számított esemény | Idő |
| --- | ---: |
| Python belépési pont; OS/bootloader/Python/runtimehook együtt | 102.117 ms |
| Első indítóképernyő | 349.874 ms |
| Főablak látható | 523.043 ms |

A Python belépési pont után mért nagyobb szakaszok:

| Fázis | Idő |
| --- | ---: |
| Splash létrehozása és első festése, ikonerőforrásokkal együtt | 202.075 ms |
| Ebből ikonerőforrások megnyitása | 9.916 ms |
| PDF/nyomtatás/főablak modulimportok | 69.312 ms |
| QtWidgets és QApplication | 33.977 ms |
| Főablak felépítése | 32.549 ms |
| Beállítások betöltése | 7.828 ms |
| Helyi ZIP-index betöltése | 0.699 ms |
| Első automatikus frissítés | 5.707 ms |

Ebben a mintában a legnagyobb külön mért GUI-szakasz az első splash-festés/fontinicializálás, utána a PDF/nyomtatás modulimportja. A főablak felépítése körülbelül 33 ms; az ikonok gyorsítótárazottak. Több másodperces helyi inicializálási elakadást ezen a runneren nem tapasztaltunk. A splash időmérése tartalmazza az ikonidőt; a táblázat sorai nem adhatók egyszerűen össze. A becsomagolt QtCore import 0,009 ms-os újraimportja nem a teljes natív betöltést jelenti: a PyInstaller runtimehookjai a belépési pont előtt is tölthetnek modulokat, ami a külső, együttes időbe tartozik. Nem állítunk külön megmért bootloader- vagy Python-inicializálási időt.

A két másodperccel késleltetett hálózati munkaszál próbájában a főablak a Python belépési pont után **424.754 ms**-nál már látható volt, a betöltés **2439.688 ms**-nál fejeződött be. A felület a hálózati feladat eredményétől függetlenül jelent meg. Nem elérhető mappákkal és hibás JSON-konfigurációval is sikeres az indulás.

A részletes gépi eredmények a ZIP-ben: `test-results.xml`, `modern-runner-selftest.json`, `startup-validation.json`, `native-dependencies.json`, `icon-audit.json`. Az indulási jelentés nem tartalmaz felhasználónevet, fájlútvonalat vagy PDF-adatot.

## Példányvédelem és megmaradó átvételi feladatok

A próba a második normál indítást, az inicializálás alatti második indítást, a gyors dupla indítást, külön mappába másolt teljes alkalmazást, a normál bezárást és a folyamatkilövés utáni újraindítást is ellenőrizte. Windowson az élő, megjelölt főablakok számát és tulajdonos PID-jét is ellenőriztük: egyetlen főablak marad. A fókusz tényleges átadását a Windows megakadályozhatja; ez nem indít új főablakot.

A védelem a 2.4-es és az azonos protokollt használó későbbi verziók között működik. A régi 2.3 EXE nem ismeri a mutexet, ezért minden használt mappát/parancsikont frissíteni kell. A beállítások változatlanul `%APPDATA%\EDPD\settings.json` alatt maradnak.

A friss rendszerindítás utáni, munkahelyi víruskeresővel és tényleges H:/G:/SMB meghajtókkal végzett hidegindítást ez a CI nem helyettesíti. A modern runner sikere nem valódi Windows 10 1607 célgépes bizonyíték (`windows1607_verified=false`). A fizikai nyomtató és több munkaállomásos hálózat átvétele továbbra is célgépes feladat. [Indítási módszertan](STARTUP.md), [Windows átvételi próba](WINDOWS-VALIDATION.md).

A KDE Modern Classic valódi upstream fájljai maguk AI-segített rekonstrukciók; ezt a forrás README/AUTHORS szövegével együtt megőrizzük és nyíltan dokumentáljuk. [Ikoneredet és licencek](ICON-THEMES.md), [összehasonlító kép](icon-theme-comparison.png).
