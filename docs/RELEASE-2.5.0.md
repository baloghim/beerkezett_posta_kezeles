# EDPD Menedzser 2.5.0 – ellenőrzött Windows-kiadás

Ellenőrizve: 2026. november 13. A kiadást a nyilvános GitHub Release ZIP tényleges letöltése és ellenőrzése után minősítettük elkészültnek.

- Forráscommit: `485077e`, címke: `v2.5.0`.
- Meglévő Windows workflow: https://github.com/baloghim/beerkezett_posta_kezeles/actions/runs/43434945716
- Release: https://github.com/baloghim/beerkezett_posta_kezeles/releases/tag/v2.5.0
- Közvetlen letöltés: https://github.com/baloghim/beerkezett_posta_kezeles/releases/download/v2.5.0/EDPD-Manager-Windows-x64.zip
- ZIP: **63735906 bájt**; a teljes ZIP CRC-vizsgálata sikeres.
- SHA-256: `b7721a29a5d3cb666bc4f5275db1db979ddc20446aa2c38857af2241a324631f`; egyezik a közzétett `.sha256` fájllal.
- Windows JUnit: **145 teszt, 0 sikertelen, 0 hiba, 0 kihagyott**; natív Windows Qt-platformmal futtatva.
- Csomagolt EXE: **17 sikeres funkcionális önellenőrzés**, `host.frozen=true`, verzió **2.5.0**.
- További **11 sikeres valódi EXE-indítási ellenőrzés**: példányvédelem, külön mappák, lassú/hiányzó mappák, hibás konfiguráció, normál és rendellenes leállás utáni újraindítás, öt mentett ikontéma.
- Natív DLL-audit: **109 bináris**, üres hibalista.
- **433 ikonerőforrás és 18 licencfájl** bájtról bájtra egyezik a forrással. Az EXE ICO hét képkockája változatlan.
- Helyi teljes Linux-regresszió: **143 sikeres, 1 Windows-specifikus vizsgálat kihagyva**; az ezt követő célzott ellenőrzések is sikeresek.

## A 2.5 javításainak ellenőrzése

| Ellenőrzés | Tényleges csomagolt eredmény |
| --- | --- |
| Főablak címe | `EDPD Menedzser 2.5.0` |
| Névjegy címe | `EDPD Menedzser – Névjegy` |
| Normál alapbetű | 8.25 pont |
| Fő eszköztár | 10.25 pont, pontosan +2 pont |
| PDF-eszköztár | 8.25 pont, az alapméret megmaradt |
| Szélesség–Teljes oldal gombköz | 8 képpont |
| Nyomtatás–PDF mentése gombköz | 8 képpont |

A fontméret a rendszer alapbetűjéből indul; nem rögzítjük minden gépen ugyanarra az értékre. Az összehasonlítás a beállított pontméretet használja. A táblázatok saját natív alapbetűje különbözhet az alkalmazás alapbetűjétől. A térközpróba a Fusion stílusban, elegendő panelszélesség mellett, ténylegesen látható gombokat mér; más gyári Qt-stílus eltérő alapmargót adhat, a 6 pixeles hozzáadott hézag ugyanaz marad.

A közös `DISPLAY_NAME` az EDPD Menedzser nevet adja a címsornak, a Névjegynek, a splashnek, az indulás alatti második példány natív jelzésének, a fő hibaablaknak és a parancssori leírásnak. A felhasználói dokumentáció is frissült. Az EXE fájlneve, az ICO, a mutex/protokoll azonosítója és a `%APPDATA%\EDPD\settings.json` útvonal megmaradt. Régi minimális és 2.4-es, megjelenési beállításokat tartalmazó JSON-fájlok betöltését is teszteltük.

A lapozás a renderelés után azonnal, majd a Qt késleltetett elrendezésének végén is alaphelyzetbe állítja a függőleges és vízszintes görgetést. Az újraállítás nem kér új PDF-renderelést. A kézi nagyítás és a nézetmód megmarad; a Szélesség és Teljes oldal mód továbbra is az adott laphoz igazít. Az Első/Előző/Következő/Utolsó műveletek, a közvetlen `move()` hívás és a határokon túli lapozás is tesztelve van. A csomagolt EXE-ben a négy gombpróba mind 0/0 görgetési pozíciót és változatlan kézi nagyítást adott.

A fájlkezelési, PDF-mentési és nyomtatási szolgáltatások, a konfiguráció adatmodellje és a PyInstaller spec nem változott a 2.4-hez képest. A tranzakciós megszakítás/visszaállítás, az eredeti PDF exportja, a helyi Feldolgozva jelölések, az időszakszűrés és az öt ikontéma regressziói is sikeresek.

A részletes gépi jelentések a ZIP-ben: `test-results.xml`, `modern-runner-selftest.json`, `startup-validation.json`, `native-dependencies.json`, `icon-audit.json`.

## Célgépes átvétel

A tényleges EXE a modern Windows Server 2022 runneren futott, Python 3.10.11 / Qt 5.15.2 / PySide2 5.15.2.1 / PyMuPDF 1.23.26 alapon. Ez nem valódi Windows 10 1607 célgépes bizonyíték (`windows1607_verified=false`). Az új EXE 17 pontos önellenőrzését a céges 1607-es gépen külön is le kell futtatni; a fizikai nyomtató és az éles hálózati környezet átvételét a CI nem helyettesíti. Minden automatikus próba mesterséges dokumentumokat és külön ideiglenes mappákat használt.

[Windows átvételi útmutató](WINDOWS-VALIDATION.md) · [1607-es önellenőrzés](WINDOWS1607.md) · [Indítás és példányvédelem](STARTUP.md)
