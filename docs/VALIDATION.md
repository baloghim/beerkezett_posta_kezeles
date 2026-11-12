# EDPD 2.0.0 – ellenőrzési eredmények

Dátum: 2026. november 12.

## Tesztek és kiadás

- Linux, Python 3.10.22: **68 sikeres teszt, 1 szabályosan kihagyott Windows-specifikus PE-teszt**.
- Windows Server 2022 runner, Python 3.10.11 x64: az automatikus tesztcsomag, a statikus DLL-audit és a ténylegesen csomagolt EXE kilenc funkcionális önellenőrzése sikeres.
- [Végleges Windows build](https://github.com/baloghim/beerkezett_posta_kezeles/actions/runs/43238330788): **Success**.
- [v2.0.0 build és Release](https://github.com/baloghim/beerkezett_posta_kezeles/actions/runs/43238754326): **Success**.
- [Release](https://github.com/baloghim/beerkezett_posta_kezeles/releases/tag/v2.0.0) · [Windows ZIP](https://github.com/baloghim/beerkezett_posta_kezeles/releases/download/v2.0.0/EDPD-Manager-Windows-x64.zip) · [SHA-256](https://github.com/baloghim/beerkezett_posta_kezeles/releases/download/v2.0.0/EDPD-Manager-Windows-x64.zip.sha256).

## A 2.0 működését igazoló tesztek

- A 14/30/90/180 napos időszak a mai nappal együtt értendő, jövőbeli és túl régi csomag nélkül; az Összes nézet teljes. A ZIP-megnyitás figyelésével ellenőriztük, hogy az időablakon kívüli ZIP-ek nem nyílnak meg a szűrt listához. Listázás és indexelés nem olvas PDF-tartalmat.
- A helyi index újraindítás után is felhasználható, változatlan régi ZIP-et nem nyit újra. A megváltozott vagy sérült index újraépül; átmeneti olvasási hiba után a frissítés fájlmódosítás nélkül is újrapróbálkozik. Az észlelt valódi ZIP-változás érvényteleníti a régi rekordot akkor is, ha a méret/időbélyeg megmaradt.
- Meghajtóbetűjelek, ismételt elválasztójelek, UNC és kiterjesztett UNC előtag, ékezetes fájlnevek és konfiguráció-visszatöltés ellenőrizve. A forrás másik aliasa alatt sem hozható létre közös állapotmappa. A ZIP-index sem írhat a forrásba.
- Az Elvégezve jelölés megmarad, visszavonható, több kliens frissítésével látható. Két külön folyamat egyidejű mentésének eredménye mindkét napi jelölést tartalmazta. Sérült közös JSON és sikertelen atomikus csere nem törölte a korábbi állapotot; az átmeneti Windows megosztási hibát is vizsgáltuk.
- A tényleges Qt-sorok zöld/félkövér fekete/részleges színezése és a jelölés elsőbbsége ellenőrizve. A kijelölés kontrasztos.
- Az alsó panel teljes munkamappa-listája független a felső kijelöléstől. Régi, ismeretlen és többértelmű eredet ellenőrizve. A felső navigálás és frissítés megőrizte a megnyitott PDF-et és oldalszámot. Elérhetetlen forrás mellett a hozzáférhető munkamappa PDF-je olvasható maradt, a módosítások letiltódtak.
- Hat napi dokumentumból négy jelen lévőnél a párbeszéd négy törlendő PDF-et jelzett, és csak ezt a négyet távolította el. Más napok fájljai és a kézi jelölés megmaradtak. Időszakon kívüli ZIP névütközése is leállította a bizonytalan napi törlést. A teljes ürítés egyéb fájltípust és jelölést nem módosított.
- A Viewer képességkészlet nem törölhet, írhat felül vagy jelölhet elvégzettnek. A korábbi PDF-renderelési, lapozási, nyomtatási oldalintervallum-, megszakítás-, hibás ZIP/PDF-, útvonalbiztonsági és többfolyamatos zártesztek is sikeresek.

## A közzétett ZIP ellenőrzése

- Méret: **61,311,349 bájt**, 198 ZIP-bejegyzés.
- Teljes ZIP CRC-ellenőrzés: hibátlan.
- A közzétett SHA-256 fájl és a letöltött ZIP egyezik: `4a13ac475d6c1c4e088b41ff2ae8c967d7cc66c79a675404a87a69ae1c78be47`.
- **107 natív PE-fájl** auditja hibátlan; x64 architektúra, név szerinti belső importok és runtime-eredet ellenőrizve. A szükséges alkalmazás-, Qt-, Python-, MuPDF- és VC DLL-ek – köztük CONCRT140.dll – mind megtalálhatók.
- Nincs Qt 6/PySide6 a csomagban. A célgépes PowerShell-script UTF-8 BOM-ja megmaradt.

A letöltött csomag `modern-runner-selftest.json` jelentése **application_version: 2.0.0**, `passed: true`, `frozen: true`, `error: null`. A kilenc sikeres ellenőrzés: natív importok; GUI és ZIP-lista; ZIP-ből PDF-betekintés/lapozás/nagyítás; munkamappa-zár; kicsomagolás és munkamappabeli betekintés; teljes oldalak nyomtatási PDF-kimenete; napi törlés/ürítés; közös jelölés és visszavonás; helyi beállítások/elrendezés.

## Windows 10 1607: mi igazolt, mi vár még próbára?

A natív verziók változatlanok: Windows Python **3.10.11 x64**, PySide2 **5.15.2.1 / Qt 5.15.2**, PyMuPDF **1.23.26**, PyMuPDFb **1.23.22**, a korábban bevált PyInstaller és alkalmazáslokális runtime-készlet.

A felhasználó korábban a **0.2.1** kiadásról küldött `EDPD-1607.json` eredményt: valódi Windows 10 x64, build **14393**, munkaállomás, `frozen: true`, nyolc sikeres funkcionális ellenőrzés és `windows1607_verified: true`. Ez a technológiai alap célgépes referenciája.

**Az új 2.0.0 célgépes eredménye még nem áll rendelkezésre.** A kiadott 2.0 EXE próbája Windows Server 2022 build **20348** gépen futott; jelentésében helyesen **windows1607_verified: false** maradt. A külön 1607-es self-hosted job nem futott. Modern runner eredményét nem tekintjük tényleges 1607-es bizonyítéknak.

A céges gépen a [Python nélkül futtatható új EXE-önellenőrzés](WINDOWS1607.md) szükséges. Ezen túl a fizikai nyomtató, a valós archívum mennyiségével mért hálózati betöltés, a többgépes SMB-kicsomagolás/törlés és a közös jelölések valódi vállalati fájlszerveren történő egyidejű mentése, valamint hálózati megszakítása vizsgálandó a [munkahelyi átvételi útmutató](WINDOWS-VALIDATION.md) szerint.

Az automatikus tesztek kizárólag ideiglenes, szintetikus adatokat és külön tesztprofilokat használtak. Éles NEAK mappákban nem végeztek műveletet.
