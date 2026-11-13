# EDPD 2.0.1 – ellenőrzési eredmények

A `v2.0.1` kiadás a `3fdb93d` commitból készült. A [kiadási workflow](https://github.com/baloghim/beerkezett_posta_kezeles/actions/runs/43248907946) sikeresen lefutott; a [közvetlen Windows x64 ZIP](https://github.com/baloghim/beerkezett_posta_kezeles/releases/download/v2.0.1/EDPD-Manager-Windows-x64.zip) ténylegesen elérhető, letöltése és ellenőrzése megtörtént.

## Automatikus eredmények

- Linux, Python 3.10 / Qt 5: **77 sikeres**, 1 szabályosan kihagyott Windows-specifikus PE-teszt.
- Windows runner, Python 3.10.11: **78 sikeres, 0 sikertelen, 0 kihagyott** teszt, 14,349 másodperc. A ZIP-ben szereplő `test-results.xml` tartalmazza a mérési adatokat.
- 1000 ZIP valódi Qt-felületes mérésénél 14/30/90/180/Összes beállításra rendre **14/30/90/180/1000 ZIP-megnyitás és napi sor**, **0 időszakon kívüli megnyitás**. Az üresjárat és az automatikus frissítés sem indított történeti beolvasást. Linuxon és Windowson azonos eredmény.
- A háromnapos valódi felületi munkafolyamatban a napváltásoknál változatlan 6 alsó sor, kicsomagolás után 12, napi törlés után 6, ürítés után 0 sor. A forrás-ZIP-ek, CSV és almappa megmaradtak.
- A becsomagolt `EDPD-Manager.exe` tényleges indítása **tíz sikeres ellenőrzést** adott: natív importok; hárompaneles GUI és ZIP-lista; független munkamappa és Forrásnap; ZIP-betekintés/lapozás/nagyítás; fájlzár; kicsomagolás és munkamappa-PDF; teljes oldalak PDF-nyomtatása; napi törlés/ürítés; beállítások/elrendezés megőrzése.
- A csomagolt felület jelentése szerint a címsor `EDPD 2.0.1 – Postai dokumentumkezelő`, az alsó cím `A munkamappa dokumentumai`, az oszlopok `Fájlnév`, `Méret`, `Forrásnap`, az időszak 14 nap. Üres munkamappánál minden felső kijelöléssel üres a lista, valódi célfájl létrehozásakor az megjelenik.
- A csomagolt indulási próba 4 érvényes ZIP-ből csak 3 időszakon belülit olvasott, 2 napi sort adott; a történeti ZIP-et és a hibás nevű állományt nem nyitotta meg.
- Statikus DLL-audit: **107 x64 natív bináris, 0 hiba**. A Qt5/Python/MuPDF és az alkalmazáslokális VC-runtime jelen van; Qt6-szennyeződés nincs.

Részletes okfeltárás: [1000 ZIP-es Qt-mérések és kritikus javítások](CRITICAL-FIXES.md).

## A közzétett ZIP ellenőrzése

- Méret: **61 315 880 bájt**.
- SHA-256: `9c0fbff2932dfe766f3591525f94784cf84f4406ef9edee46fae57b9a3ad2c98`; egyezik a kiadott `.sha256` fájllal.
- ZIP CRC-vizsgálat hibátlan; az EXE érvényes PE-fejléccel rendelkezik. A `Test-Windows1607.ps1` UTF-8 BOM-os, Windows PowerShell 5.1 alatt is olvasható.
- A ZIP tartalmazza a modern runner önellenőrzését, a natív leltárt és a teljes JUnit XML-t. Az önellenőrzés `application_version` mezője **2.0.1**, `host.frozen` igaz, `windows1607_verified` **hamis**.

## A célgépes bizonyíték határa

A friss EXE-próba Windows Server build **20348** modern runneren futott, nem Windows 10 1607-en. Ez az eredmény és a statikus DLL-audit **nem bizonyítja a 1607-es futást**. Az opcionális, valódi 1607-es self-hosted workflow megmaradt, de ilyen runner nem állt rendelkezésre.

A natív verziók változatlanok. A régebbi 0.2.1 célgépes JSON-próbája és a felhasználó 2.0-s indításról adott visszajelzése nem helyettesíti az új 2.0.1 célgépes önellenőrzést, a fizikai nyomtató és a többgépes SMB próbáját.
