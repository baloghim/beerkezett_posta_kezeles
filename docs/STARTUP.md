# EDPD Menedzser – indítás és egyetlen példány

## Az indítás változásai és mérése

A 2.3-as belépési pont a PDF- és nyomtatási modulokat, majd a teljes főablakot a QApplication és bármilyen látható visszajelzés előtt töltötte be. Az ikonlekérések ugyanazokat a fájlokat soronként újra ellenőrizték és új QIcon objektumokat készítettek. Az aktuális EDPD Menedzser először megszerzi a példányzárat, elindítja a Qt-t, és megmutatja az egyszerű Crystal megjelenésű „EDPD Menedzser / A program indítása…” indítóképernyőt. A PDF/nyomtatás importja és a főablak létrehozása ezután következik. A splash a főablak megjelenésekor eltűnik. A témakezelő ugyanazt az ikont szerepenként csak egyszer tölti be egy témában.

A mappák hálózati elérése, a helyi ZIP-index betöltése, az időszakon belüli ZIP-ek feldolgozása és a munkamappa felsorolása háttérfeladatban marad. Az első frissítést a főablak megmutatása után ütemezzük. A státusz ekkor „Dokumentumok és napi csomagok betöltése…”, majd az eredmény automatikusan megjelenik. A 2.3-ban már meglévő időszakszűrés és index változatlanul elkerüli a teljes történeti ZIP-állomány megnyitását. Pusztán ikon/Qt-stílus váltásakor nincs hálózati útvonalellenőrzés és új ZIP-olvasás.

A `startup-last.json` fájl a `%LOCALAPPDATA%\EDPD` mappában tartalmazza a legutóbbi indulás idejét; nem tartalmaz útvonalat, felhasználónevet, PDF-tartalmat vagy nyers hibaüzenetet. Az alapértelmezett jelentést háttérszál írja, a főablak megjelenését nem késlelteti. Hibás konfigurációnál csak a kivétel osztálya, például JSONDecodeError szerepel; a program alapértékekkel indul és érthető figyelmeztetést mutat.

Mért fázisok: példányzár; QtCore; QtWidgets és QApplication; ikonerőforrások; splash; beállítások; megjelenés; PDF/nyomtatás/főablak modulok importja; főablak felépítése; cél- és forrásmappa ellenőrzése; helyi ZIP-index; ZIP-katalógus; szűrt ZIP-feldolgozás; első automatikus frissítés. Külön eseményidő a splash és a főablak megjelenése, valamint a háttérbetöltés kezdete/vége. A JSON-idők ezredmásodpercben értendők; az egymásba ágyazott méréseket nem szabad összeadni.

A PyInstaller/Windows betöltő és a Python inicializálása a Python belépési pont előtt fut. Ezeket belülről nem lehet visszamenőleg külön-külön megmérni. A külső teszt a folyamatindítástól a Python belépési pontjáig, a splashig és a főablakig is mér. Az előbbi a folyamat/bootloader/Python együttes ideje, nem kizárólag PyInstaller-idő.

A kiadás tényleges Windows-mérései és a leglassabb fázisok a ZIP `startup-validation.json` fájljában, a [2.4.0 részletes indulási mérésében](RELEASE-2.4.0.md) és a [2.6.0 kiadásellenőrzésében](RELEASE-2.6.0.md) találhatók. Az új folyamat/új profil nem azonos az operációs rendszer teljesen hideg fájlgyorsítótárával. A CI nem üríti a Windows fájlgyorsítótárát, és nem modellezi az adott munkahely víruskeresőjének első EXE-vizsgálatát. A munkahelyi hideg indítást friss rendszerindítás után külön is mérni kell ugyanilyen jelentéssel.

## Felhasználónként és Windows-munkamenetenként egy példány

A `Local\EDPD.Manager.<azonosító>` névvel ellátott Windows mutex a Qt importja előtt létrejön. Az azonosító a bejelentkezett felhasználót és egy állandó alkalmazásprotokoll-nevet használ; nincs benne EXE-útvonal, telepítési mappa vagy verziószám. A külön mappába másolt 2.4-es és újabb alkalmazások ugyanazt a példányt találják meg. Másik felhasználó vagy másik Windows-munkamenet külön példányt használhat.

A futó főablakot Win32 ablakproperty azonosítja. A második indítás nem tölt Qt-t és nem épít második főablakot; helyreállítja a minimalizált ablakot és előtérbe hozza, ha a Windows engedi. Az előtérbe kerülést a Windows fókuszvédelme megakadályozhatja. Ha még nincs főablak, rövid natív „Az EDPD Menedzser már indul…” jelzés jelenik meg, majd a második folyamat kilép. A második indítás nem írja át a beállításokat.

Normál kilépés felszabadítja a mutexet. Folyamatkilövéskor a Windows megszünteti/elhagyottnak jelöli a tulajdonjogot, így nincs kézzel törlendő, tartós zár. Linux-fejlesztői tesztben felhasználói/sessionazonosítóval védett flock és helyi Unix socket szolgál ugyanerre. A normál beállításútvonal változatlan: `%APPDATA%\EDPD\settings.json`.

A `--self-test` és a `--recover-extraction` módok nem veszik fel a GUI-példányzárat. A 2.4 előtti, példányvédelem nélküli EXE-t utólag nem lehet rákényszeríteni az új protokollra: régi EXE és új EXE egyidejű használata ellen az új mutex önmagában nem nyújt védelmet. Minden használt telepítési mappát frissíteni kell.

## Automatizált valódi folyamatpróbák

A `tests/test_startup.py` friss Python-folyamatokkal futtatja a `scripts/check_startup.py` teszthajtóját. Ugyanez a meglévő Windows buildworkflow részeként az **újonnan csomagolt EXE-t** indítja el, valódi Win32 ablakokkal. A Windows-próba a teljes alkalmazást másik mappába is lemásolja. Minden próba izolált, mesterséges helyi profil/mappákat használ.

```powershell
python scripts/check_startup.py dist/EDPD-Manager/EDPD-Manager.exe --report startup-validation.json
```

Ellenőrzések: első indítás új profillal; második indítás élő főablak mellett; külön telepítési mappák; gyors dupla indítás és indulás alatti második indítás; mesterségesen két másodperccel késleltetett hálózati munkaszál; nem elérhető forrás/cél; hibás JSON; az öt mentett ikontéma tényleges újraindításban; normál kilépés utáni és folyamatkilövés utáni újraindítás. A késleltetett munkaszálas próba ellenőrzi, hogy a főablak legalább 1,9 másodperccel a háttérbetöltés vége előtt látható.

Az időmérés kézzel is kérhető: `EDPD-Manager.exe --startup-report <jelentés.json>`. Az automatikus bezárás és mesterséges késleltetés kapcsolói csak külön jelentéssel és pozitív `--startup-exit-ms` értékkel használhatók tesztmódban; a mindennapos indításhoz nincs szükség rájuk.
