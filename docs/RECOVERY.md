# EDPD Menedzser – kicsomagolás megszakítása és helyreállítása

A Mégse, az Escape és a folyamatablak bezárási kísérlete megszakítási kérelmet
küld a háttérszálnak. Nem állítjuk le erőszakkal a szálat. A folyamatablak addig
nyitva marad, amíg a visszavonás vagy a helyreállítási kísérlet befejeződik.
Egy blokkoló Windows/SMB hívás az operációs rendszer időtúllépéséig eltarthat.

## A művelet menete

1. A munkamappa közös `.edpd-operation.lock` zárának megszerzése, a napi ZIP és
   a jóváhagyott célállapot újbóli ellenőrzése. A történeti ütközésvizsgálat megmarad.
2. Saját `.edpd-recovery-<véletlen azonosító>` könyvtár létrehozása a munkamappában.
3. Az összes szükséges PDF teljes kibontása és CRC-ellenőrzése, fsync az előkészített
   fájlokra. Felülírásnál az eredeti fájlok ellenőrzött biztonsági másolatának megőrzése.
4. Tartós `journal.json` napló; ellenőrzött, fájlonkénti véglegesítés. Új fájlt nem
   írunk felül észrevétlenül. A zár a teljes művelet és a visszavonás alatt megmarad.
5. Megszakítás vagy hiba esetén fordított sorrendű visszavonás. A saját új fájlok
   törlése és az eredeti tartalmak visszaállítása előtt méret/időbélyeg/fájlazonosság
   és SHA-256 ellenőrzés történik. Közben megváltozott célfájlt nem törlünk vagy írunk felül.
6. Sikeres művelet vagy teljes visszavonás után a saját technikai könyvtár törlése.
   A kihagyott, korábban létező PDF-ek érintetlenek maradnak.

Az előkészítés és a véglegesítés külön fázisként, tényleges fájlszámmal jelenik meg.
A helyigény az új adatok és az esetleges eredeti biztonsági másolatok mérete;
nincs teljes napi, többfájlos atomi Windows/SMB tranzakció. Nem ígérünk garantált
visszaállítást áramszünet, folyamatkilövés, hálózati szakadás vagy hozzáférési hiba esetén.

## Ha helyreállítási könyvtár maradt

A hibaüzenet felsorolja az érintett fájlokat és a megőrzött könyvtár pontos helyét.
A program új kicsomagolást és törlést sem enged, amíg ilyen könyvtár van a célban.
A PDF-lista olvasható marad. A könyvtár dokumentumadatot, eredeti biztonsági
másolatot és naplót tartalmaz: ne törölje automatikusan, és ne tegye külső szolgáltatásra.

Előbb állítsa le a többi kliens módosító műveleteit és biztosítsa a hálózati
hozzáférést. Ellenőrizze, hogy a program beállított munkamappája a helyreállítandó
könyvtár szülője. Újra megkísérelhető a helyreállítás:

```bat
EDPD-Manager.exe --recover-extraction "G:\teszt-munkamappa\.edpd-recovery-azonosito"
```

Forrásból ugyanígy: `python -m edpd.main --recover-extraction "<könyvtár>"`.
A parancs ellenőrzi a naplót, a célútvonalat, a biztonsági másolatokat, és a közös
munkamappazár alatt dolgozik. A forrásarchívumban ez sem végezhet írást.
Az eredmény külön tájékoztató vagy részletes hibaablakban jelenik meg.

Másik alkalmazás által megváltoztatott vagy bizonytalan véglegesítési állapotú
fájlt a helyreállító sem módosít automatikusan. Ilyenkor kezelői ellenőrzés szükséges:
őrizze meg a megváltozott fájl külön másolatát és a teljes helyreállítási könyvtárat,
majd a napló alapján azonosítsa az eredeti és az új állapotot. Ne írja át a naplót
vakon. A biztonsági másolatokat csak az eredmény ellenőrzése után távolítsa el.
A már véglegesített, csak takarításra váró napló esetén a helyreállító nem vonja
vissza a kész dokumentumokat, csak a technikai könyvtárat takarítja.

A forrás ZIP-ek, a helyi Feldolgozva jelölések és a műveletben nem érintett
munkamappabeli fájlok egyik lépésben sem módosulnak.
