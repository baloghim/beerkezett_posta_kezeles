# EDPD 2.0 – ellenőrzési eredmények

A fejlesztés ugyanazokat a Windows 1607-kompatibilis natív függőségeket használja: Python 3.10.11 Windows x64, PySide2 5.15.2.1 / Qt 5.15.2, PyMuPDF 1.23.26 és PyMuPDFb 1.23.22. Új külső függőség nincs.

A 2.0 tesztjei, a Windows build és a kiadás ellenőrzése folyamatban. A végleges eredményeket a sikeres futás és a közzétett ZIP letöltés utáni ellenőrzése után rögzítjük.

A korábbi 0.2.1 kiadásról a felhasználó által küldött `EDPD-1607.json` valódi Windows 10 x64, build 14393 munkaállomást, `frozen: true`, nyolc sikeres funkcionális ellenőrzést és `windows1607_verified: true` eredményt igazolt. Ez a technológiai alap referenciája; **nem az új 2.0 célgépes futtatásának eredménye**.

A 2.0 új, kilenc ellenőrzéses EXE-önellenőrzése külön vizsgálja a közös Elvégezve jelölés mentését és visszavonását. A fizikai nyomtató, a többgépes SMB-módosítások és a közös állapotfájl valós vállalati hálózati próbája még szükséges. Az automatikus tesztek kizárólag ideiglenes, szintetikus adatokkal dolgoznak, az éles NEAK mappákban semmit nem módosítanak.
