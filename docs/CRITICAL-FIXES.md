# EDPD 2.0.1 – kritikus adatbetöltési javítás

## Az igazolt okok és a javítás

A 2.0.0 felső listája már a ZIP-megnyitás előtt szűrt, de `MainWindow.finish_job` nem üres munkamappa és hiányos index esetén automatikusan elindította az `origin_timer` feladatát. Az 8 ZIP-es adagokkal végül a teljes történeti archívumot bejárta. Ez a rejtett második feldolgozás a 14 napos listától függetlenül jelentős hálózati forgalmat okozott.

A régi keresés most kizárólag a **További forráskeresés** gombbal engedélyezhető. Indulás, frissítés és napváltás nem ad ilyen engedélyt. A beállított időszak szűrése továbbra is a fájlnév dátumán, a ZIP megnyitása előtt történik. Az automatikus frissítés csak a beállított időszak ZIP-jeinek érvényességét ellenőrzi.

A felső napra történő duplakattintás korábban külön, kétoszlopos ZIP-dokumentumablakot nyitott. Ez megtévesztő lehetett a munkamappa-listához képest. A ZIP-betekintés megmaradt, de külön, jobb kattintásos menüművelet lett. A kijelölés és a duplakattintás sem cseréli le az alsó táblázatot.

A korábbi forráskódban az alsó táblázat már a munkamappából épült és tartalmazta a Forrásnap oszlopot; a feltöltött hibaleírásban jelzett teljes viselkedést ezért nem tulajdonítjuk bizonyíték nélkül egy ZIP-alapú alsó frissítőfüggvénynek. A javítás ezt a szerződést külön modellekkel, tényleges Qt-táblázatos tesztekkel és a becsomagolt EXE önellenőrzésében is kikényszeríti.

A `DailyArchiveModel` / `read_daily_archives` a napi ZIP-eké; a `WorkspaceModel` / `read_workspace` kizárólag a munkamappa fájlrendszeréből olvas. Az eredetinformáció csak a már létező munkamappabeli sorok Forrásnap celláját egészíti ki, nem hozhat létre ZIP-beli fájlsort. Az oszlopok: **Fájlnév, Méret, Forrásnap**. A fájlnév rugalmasan méreteződik, teljes szövege buboréksúgóban olvasható; hosszú név sem tolja ki a harmadik oszlopot.

Az Összes nézetnél talált Qt-szűk keresztmetszetet is javítottuk: az elemek formázása beszúrás előtt készül, a tömeges sorfeltöltés alatt az automatikus oszlopméretezés és rajzolás szünetel, majd egyetlen méretezés történik. Az alapelrendezés, arculat és natív keretrendszer változatlan.

## Kötelező grafikus mérés: 1000 valódi teszt-ZIP

A tesztarchívum 1000 egymást követő napot, három naptári évet fed le. A célban egy ismeretlen eredetű PDF is van, hogy a korábbi automatikus keresés feltételét is előállítsuk. A teszt az indulás befejezése után is feldolgozza a Qt-eseményeket, majd automatikus frissítést indít. Minden ZIP-megnyitást számol, a PDF-tartalom olvasását tiltja, és a tényleges Qt-tábla dátumait vizsgálja.

| Időszak | Összes ZIP | Időszakon belüli ZIP | Tényleges megnyitás | Felső napi sor | Időszakon kívüli megnyitás |
| --- | ---: | ---: | ---: | ---: | ---: |
| 14 nap | 1000 | 14 | 14 | 14 | 0 |
| 30 nap | 1000 | 30 | 30 | 30 | 0 |
| 90 nap | 1000 | 90 | 90 | 90 | 0 |
| 180 nap | 1000 | 180 | 180 | 180 | 0 |
| Összes | 1000 | 1000 | 1000 | 1000 | 0 |

A változatlan ZIP-ek második, automatikus frissítése nem növeli a megnyitásszámot. Ez a tesztadatokra vonatkozó mérés; éles hálózati másodpercekre nem következtetünk belőle. Több ZIP egy napon természetesen több megnyitást, de egy napi sort jelent.

A külön munkamappa-teszt három napot választ ki egymás után, hat változatlan alsó PDF-sorral és változatlan munkamappamodellel, új munkamappa-olvasás nélkül. A második nap kicsomagolása 12-re növeli, annak törlése 6-ra csökkenti, az ürítés 0-ra csökkenti a tényleges táblázatsorokat. Az Elvégezve jelölés megmarad, a forrás ZIP-ek és más fájltípusok változatlanok.

A Forrásnap-tesztek lefedik az ismert napot, a korábban indexelt régi PDF-et, az Ismeretlen és Több lehetséges nap megjelenést, az index érvénytelenítését és az ismeretlen eredetű PDF megnyitását. A korábbi nyomtatási és fájlműveleti tesztek is megmaradnak.

## Kiadhatóság és célgép

A kiadási workflow JUnit XML-ben megőrzi a mért számokat. A becsomagolt EXE tíz ellenőrzése között külön vizsgálat ellenőrzi a munkamappa-címet, a három oszlopot, az üres cél üres tábláját minden felső kijelölésnél, a valódi célfájl megjelenését, valamint egy történeti ZIP kizárását az induló feldolgozásból. A jelentés pontos alkalmazásverziót is tartalmaz.

A Python 3.10.11 / Qt 5.15.2 / PyMuPDF 1.23.26 natív alap, az Elvégezve tárolása és a fájlműveletek hatóköre változatlan. A Windows 10 1607-en a 2.0.1 új önellenőrzése és a valódi SMB/nyomtatópróba még szükséges; modern runneren sikeres futást nem tekintünk célgépes bizonyítéknak.
