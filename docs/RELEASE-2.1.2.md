# EDPD 2.1.2 – közzétett Windows-kiadás ellenőrzése

- Forráscommit: `f605b01`, kiadási címke: `v2.1.2`.
- A meglévő Windows GitHub Actions workflow sikeres: https://github.com/baloghim/beerkezett_posta_kezeles/actions/runs/43390679185
- Release: https://github.com/baloghim/beerkezett_posta_kezeles/releases/tag/v2.1.2
- Ellenőrzött letöltés: https://github.com/baloghim/beerkezett_posta_kezeles/releases/download/v2.1.2/EDPD-Manager-Windows-x64.zip
- ZIP mérete: 61320840 bájt; minden ZIP-bejegyzés CRC-ellenőrzése sikeres.
- SHA-256: `0de7fb944e01a4a7916a05eb1466741eb6ea8f6ad240d30df38c7eeab4ae9a4f`. Egyezik a kiadás külön `.sha256` fájljával.
- A ZIP-ben lévő friss JUnit-jelentés: **88 teszt, 0 hiba, 0 sikertelen, 0 kihagyott**.
- A csomagolt EXE önellenőrzése: **2.1.2**, `frozen=true`, `passed=true`, mind a **10 ellenőrzés sikeres**.
- A csomagolt önellenőrzés tényleges Qt-stílusai: `windowsvista`, `Windows`, `Fusion`.
- Natív audit: **107 bináris**, `passed=true`, üres hibalista.
- Helyi Linux-regresszió: **86 sikeres teszt, 1 Windows DLL-audit kihagyva**.

A `v2.1.0` és `v2.1.1` címkék Windows-futásai a Névjegy elhelyezésének
ellenőrzésén elbuktak, ezért azokból Release nem készült. A kezdeti várakozás
javítása után a Windows-futás továbbra is kimutatta az eszköztár túlcsordulását.
A 2.1.2 ezt az elrendezést javítja; a gomb láthatóságát és jobb szélső helyét
800 és 1600 képpontos ablakszélességnél is ellenőrzi. Korábbi címkét nem írtunk át.

A sikeres modern Windows-build és a statikus audit nem bizonyítja a Windows 10
1607 célgépes kompatibilitását: a jelentés `windows1607_verified=false` értéket
rögzít. A valódi célgépes, SMB-megosztásos és fizikai nyomtatási átvétel továbbra
is szükséges. A tesztek kizárólag szintetikus adatokat használtak.
