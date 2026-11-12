# Ellenőrzési eredmények – 0.1.0

Dátum: 2026. november 12.

- Linux, Python 3.12.14: **28 sikeres pytest-teszt**, nincs sikertelen vagy kihagyott teszt. A PyMuPDF SWIG-rétege öt külső deprecációs figyelmeztetést jelzett.
- A Qt offscreen felülete ideiglenes szintetikus ZIP-ekkel elindult; a ZIP-ből történő PDF-megnyitás, lapozás, frissítés közbeni olvasás, kicsomagolás, napi törlés és ürítés működött.
- A QPrinter PDF-kimenet két teljes oldalt állított elő a kiválasztott oldalintervallumból. A nyomtatási párbeszéd megszakításának tesztje nem indított renderelést. Fizikai nyomtatót ez nem vizsgál.
- A többfolyamatos fájlzár és a kényszerleállítás utáni újrazárolás Linuxon sikeres; a Windows suite ugyanezeket a kódutakat a Windows implementációval futtatja. Valós kétgépes SMB-próba még szükséges.
- [Első Windows build](https://github.com/baloghim/beerkezett_posta_kezeles/actions/runs/43206942747): **Success**.
- [v0.1.0 Windows build és GitHub Release](https://github.com/baloghim/beerkezett_posta_kezeles/actions/runs/43207374394): **Success**.
- [Release](https://github.com/baloghim/beerkezett_posta_kezeles/releases/tag/v0.1.0) és [Windows ZIP](https://github.com/baloghim/beerkezett_posta_kezeles/releases/download/v0.1.0/EDPD-Manager-Windows-x64.zip) ténylegesen elérhető.

A letöltött csomag:

- Méret: 68 636 298 bájt; 325 ZIP-bejegyzés.
- A teljes ZIP CRC-ellenőrzése hibátlan.
- `EDPD-Manager/EDPD-Manager.exe`: Windows `MZ` fejléc jelen van.
- `EDPD-Manager/_internal/PySide6/plugins/platforms/qwindows.dll`: jelen van.
- SHA-256: `7df24e1fbee3dbba3fcbf3614e191244143b2678a2ff60587ac34cfc459e237a`

Az EXE-t ezen a Linux gépen nem futtattuk. A sikeres build és a csomagellenőrzés nem igazolja a tényleges Windows gépen, hálózati megosztáson és nyomtatón végzett működést. Az [átvételi útmutató](WINDOWS-VALIDATION.md) lépései még elvégzendők.
