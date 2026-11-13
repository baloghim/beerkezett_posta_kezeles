# EDPD 2.3.0 – ellenőrzött Windows-kiadás

- Forráscommit: `da41bcc`, kiadási címke: `v2.3.0`.
- Sikeres meglévő Windows workflow: https://github.com/baloghim/beerkezett_posta_kezeles/actions/runs/43406277712
- Release: https://github.com/baloghim/beerkezett_posta_kezeles/releases/tag/v2.3.0
- Ténylegesen letöltött ZIP: https://github.com/baloghim/beerkezett_posta_kezeles/releases/download/v2.3.0/EDPD-Manager-Windows-x64.zip
- ZIP: 63054483 bájt; minden ZIP-bejegyzés CRC-ellenőrzése sikeres.
- SHA-256: `8fb9b75770ca96fbd88e254eaaeb57b69576b89d875353842791d72238b0a731`; egyezik a közzétett `.sha256` fájllal.
- A csomag friss JUnit-jelentése: **127 teszt, 0 sikertelen, 0 hiba, 0 kihagyott**.
- A csomagolt EXE: **2.3.0**, `host.frozen=true`, `passed=true`, **13 sikeres funkcionális önellenőrzés**.
- A csomagolt felület tényleges alsó oszlopai: **Nap, Fájlnév, Méret**.
- Kipróbált gyári Qt-stílusok: `windowsvista`, `Windows`, `Fusion`.
- Natív DLL-audit: **107 bináris**, üres hibalista.
- EXE ICO: **16/24/32/48/64/128/256** pixeles képkockák, byte szerinti összevetéssel.
- **207** csomagolt grafikai/jegyzékerőforrás egyezik a forrással. A szerzői és licencfájlok a ZIP-ben jelen vannak.
- Helyi Linux-tesztek: **125 sikeres, 1 Windows DLL-audit kihagyva**.

## A 2.3-as viselkedés ellenőrzése

A 13 pontos EXE-önellenőrzés a régi regressziók mellett az eredeti PDF bájtjainak
exportját, a helyi Feldolgozva jelölést és a véglegesítés közbeni megszakítás
visszavonását is futtatja. Az új tesztek ellenőrzik a fő eszköztár méretét,
a panelcímeket, az arányos/állítható oszlopokat, a Nap szerinti csökkenő és azon
belüli név szerinti növekvő rendezést, valamint az olvasott PDF megőrzését
forrásnap-frissítés és újrarendezés után.

Külön próbák fedik le a modális folyamatablakot, a Mégse reakcióját, a működő Qt
eseményciklust, az előkészítés és a véglegesítés több pontján történő megszakítást,
az új fájlok visszavonását, az eredeti tartalmak visszaállítását, a helyreállítási
hiba utáni újrapróbálást és a másik folyamat által megváltoztatott fájl megőrzését.
A teljes napi adatot előre ellenőrizzük; a forrás ZIP-ek írásvédelme és a teljes
műveleten/visszavonáson át tartott munkamappazár megmarad.

A PDF-mentési tesztek az eredeti többoldalas bájtokat, a ZIP-betekintésből mentést,
a Mégse/felülírási megerősítés működését és az eredeti, illetve aktuális forrás- és
munkamappa kizárását is ellenőrzik. A helyi jelölések újraindítás és különböző
forrásarchívumok mellett, útvonal-aliasokon át is megmaradnak. A helyi menü a
megnyitáskor ténylegesen megcélzott napra vonatkozik. A Betekintő képességkészlet
nem enged jelölést. A közös hálózati állapotmappa nem tért vissza.

## Megmaradó korlátok

Windows/SMB alatt nincs több PDF-re kiterjedő atomi fájlrendszer-tranzakció.
Hálózati/hardverhiba, folyamatkilövés vagy külső fájlmódosítás miatt a visszaállítás
részleges maradhat. A program ilyenkor név szerint jelzi a problémát, megőrzi a
naplót és a biztonsági másolatokat, és nem törli a megváltozott célfájlt.
A blokkoló OS-hívás megvárása szükséges lehet. [Helyreállítási útmutató](RECOVERY.md).

A modern Windows runner sikere nem bizonyítja a valódi Windows 10 1607 célgépes
futtatást (`windows1607_verified=false`). A célgépes, több munkaállomásos SMB és
fizikai nyomtatási átvétel továbbra is szükséges. Minden automatikus teszt
mesterséges adatokat használt, éles NEAK-megosztáson nem futott.
