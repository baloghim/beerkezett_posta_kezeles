# EDPD 2.2.0 – ellenőrzött Windows-kiadás

- Forráscommit: `256db03`, kiadási címke: `v2.2.0`.
- Sikeres meglévő Windows workflow: https://github.com/baloghim/beerkezett_posta_kezeles/actions/runs/43395570325
- Release: https://github.com/baloghim/beerkezett_posta_kezeles/releases/tag/v2.2.0
- Ténylegesen letöltött ZIP: https://github.com/baloghim/beerkezett_posta_kezeles/releases/download/v2.2.0/EDPD-Manager-Windows-x64.zip
- ZIP: 62973510 bájt, minden CRC sikeres.
- SHA-256: `202c06d18dfc96246105b375d7dbf0abcd36b63d155263559cb73cecc4fd604d`; egyezik a külön közzétett `.sha256` fájllal.
- A ZIP friss JUnit-jelentése: **92 teszt, 0 sikertelen, 0 hiba, 0 kihagyott**.
- A csomagolt EXE: **2.2.0**, `host.frozen=true`, `passed=true`, **10 sikeres funkcionális önellenőrzés**.
- A csomagolt önellenőrzés kipróbált stílusai: `windowsvista`, `Windows`, `Fusion`.
- Natív audit: **107 bináris**, nincs hiba.
- EXE-ikon: a tényleges PE-erőforrások **16/24/32/48/64/128/256** pixeles képkockái
  byte szerint egyeznek a projekt ICO-jával. **199** csomagolt erőforrás egyezik
  a forrással; a Crystal szerzői és licencfájlok is jelen vannak a ZIP-ben.
- Helyi Linux-tesztek: **90 sikeres, 1 Windows DLL-audit kihagyva**.

A régi közös jelölési modul, beállítás, tárolás és saját tesztjei eltűntek.
A megmaradó tesztek lefedik a valódi fájlállapotokat, az 1000 ZIP-es időszakszűrést,
a célzott törlést, az önálló munkamappa-listát, a többfolyamatos fájlzárat,
a PDF-nyomtatást és az új ikonokat. Az új kicsomagolási tesztek ellenőrzik az
üres/teljes/részleges állapotot, a friss célállapotot, a felülírási versenyhelyzetet,
a dupla kattintást, az ismételt indítás tiltását, a valódi fájlszám szerinti
folyamatjelzést és a fő eseményciklus működését háttérben késleltetett fájlolvasásnál.
A csomagolt EXE önellenőrzése már a tényleges grafikus kicsomagolási útvonalat is futtatja.

A kicsomagolás előkészítése csak a kijelölt napot olvassa újra. Teljes célállapotnál
nincs történeti ZIP-olvasás. Tényleges írás előtt hideg index esetén a teljes
archívum tartalomjegyzék-ellenőrzése biztonsági okból szükséges; a változatlan
régi ZIP-ek friss méret/időbélyeggel ellenőrzött indexe újrahasznosul. Ezt a
korlátot a README is leírja.

A modern Windows runner sikere nem bizonyítja a Windows 10 1607 célgépes
kompatibilitást (`windows1607_verified=false`). A Windows tálca, Alt+Tab,
fizikai nyomtatás és többgépes SMB átvételi próbája továbbra is szükséges.
Minden automatikus próba szintetikus adatokat használt; éles megosztáson nem futott.
Az ikonok pontos eredete és a színezések/kombinációk: [ICONS.md](ICONS.md).
